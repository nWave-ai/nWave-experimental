"""SubagentStop handler — validates step completion after sub-agent returns.

Translates Claude Code's SubagentStop hook event (JSON stdin) into
SubagentStopService decisions (allow/block). Extracts DES context from
agent transcripts, manages signal file lifecycle, and emits audit events.

Extracted from claude_code_hook_adapter.py as part of P4 decomposition.
"""

import contextlib
import io
import json
import os
import re
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from des._internal import subset_parser
from des.adapters.driven.logging.audit_events import (
    AgentUsageObservedEvent,
    EventType,
)
from des.adapters.driven.time.system_time import SystemTimeProvider
from des.adapters.drivers.hooks import des_task_signal, hook_protocol, service_factory
from des.adapters.drivers.hooks.execution_log_resolver import resolve_execution_log_path
from des.adapters.drivers.hooks.hook_protocol import (
    EXIT_CODE_TO_DECISION,
    STDERR_CAPTURE_MAX_CHARS,
    log_hook_completed,
    log_hook_error,
    log_hook_invoked,
    read_and_parse_stdin,
)
from des.adapters.drivers.hooks.project_root_validator import validate_project_root
from des.adapters.drivers.hooks.skill_tracking_hooks import (
    maybe_track_skill_loads as _maybe_track_skill_loads,
)
from des.adapters.drivers.hooks.token_usage_extractor import (
    extract_token_usage_events,
)
from des.application.decision_table_traceability_gate import (
    ClauseIdFeatureParser,
    DecisionTableParser,
    DecisionTableTraceabilityGate,
)
from des.domain.atdd_pure_phases import COMMIT_GATE_PHASES as _COMMIT_GATE_PHASES
from des.domain.atdd_pure_phases import (
    FEATURE_END_RETURN_PHASE as _FEATURE_END_RETURN_PHASE,
)
from des.domain.des_marker_parser import DesMarkerParser
from des.domain.repo_path_resolver import (
    feature_delta_path as _feature_delta_path,
)
from des.domain.wave_active import WAVE_VOCABULARY
from des.ports.driven_ports.audit_log_writer import AuditEvent
from des.runtime.interpreter import des_spawn


# ---------------------------------------------------------------------------
# Transcript DES context extraction
# ---------------------------------------------------------------------------


def _normalize_message_content(content: object) -> str:
    """Normalize message content from string or list-of-text-blocks to plain string."""
    if isinstance(content, list):
        return "\n".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return content if isinstance(content, str) else ""


# A triple-backtick fenced block (``` ... ```, including ```lang fences) and an
# inline `backtick` span. A DES marker that lives ONLY inside one of these is
# documentation a read-only agent quoted, NOT a dispatch directive — so it must
# be removed before the marker parse, else it false-blocks the return (C8).
_FENCED_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`]*`")


def _strip_fenced_regions(text: str) -> str:
    """Remove fenced + inline-code spans, returning the residual prose.

    A DES marker documented inside a ``` fenced block or an inline `backtick`
    span is read-only documentation, not a directive; stripping these regions
    before the marker parse stops a documented marker from false-blocking the
    SubagentStop return. A REAL marker OUTSIDE any fence stays in the residual
    and still resolves (unbounded-preservation).
    """
    without_fences = _FENCED_BLOCK_RE.sub("", text)
    return _INLINE_CODE_RE.sub("", without_fences)


def _log_transcript_audit(
    event_type: str, transcript_path: str, **extra: object
) -> None:
    """Log a transcript-related audit event, silently swallowing failures."""
    try:
        hook_protocol.get_audit_writer().log_event(
            AuditEvent(
                event_type=event_type,
                timestamp=SystemTimeProvider().now_utc().isoformat(),
                data={"transcript_path": transcript_path, **extra},
            )
        )
    except Exception:
        pass


def extract_des_context_from_transcript(transcript_path: str) -> dict | None:
    """Extract DES markers from an agent's transcript file.

    Reads the JSONL transcript and resolves the DES dispatch context.

    Two dispatch shapes are recognised:

    * **classic** — the first user message carrying a complete classic marker
      set (``DES-PROJECT-ID`` + ``DES-STEP-ID``) wins. First-match return,
      unchanged from the pre-T-C behaviour.
    * **atdd_pure** (T-C / G-4) — a transcript may carry the ``DES-MODE:atdd_pure``
      marker block more than once (residue R7: a re-dispatched slice). The
      **last** atdd_pure block wins — it is the most recent dispatch. The
      resolved context carries ``mode``/``slice_id``/``atdd_pure_phase`` and no
      ``step_id`` (atdd_pure carries no ``DES-STEP-ID``).

    An atdd_pure block, when present anywhere in the transcript, takes
    precedence over a classic first-match — the dispatch IS an atdd_pure one.

    Args:
        transcript_path: Absolute path to the agent's transcript JSONL file

    Returns:
        For a classic dispatch: dict with "project_id", "step_id",
        "project_root". For an atdd_pure dispatch: dict with "mode",
        "project_id", "slice_id", "atdd_pure_phase", "project_root" and
        "step_id" set to None. None when no DES markers are found.
    """
    if not Path(transcript_path).exists():
        return None

    classic_context: dict | None = None
    atdd_pure_context: dict | None = None

    try:
        with open(transcript_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                message = entry.get("message", {})
                if not isinstance(message, dict):
                    continue

                # Strip fenced / inline-code regions ONCE so BOTH the
                # DES-VALIDATION presence check and the marker parse see the same
                # residual: a marker quoted inside a ``` fence or `backtick` span
                # is documentation, not a directive (C8 false-block fix).
                content = _strip_fenced_regions(
                    _normalize_message_content(message.get("content", ""))
                )
                if "DES-VALIDATION" not in content:
                    continue

                markers = DesMarkerParser().parse(content)
                if not markers.is_des_task:
                    continue

                if markers.mode == "atdd_pure":
                    # Last-match scan: each atdd_pure block overwrites the
                    # previous one so the LAST (most recent) dispatch wins.
                    if markers.project_id:
                        atdd_pure_context = {
                            "mode": "atdd_pure",
                            "project_id": markers.project_id,
                            "step_id": None,
                            "slice_id": markers.slice_id,
                            "atdd_pure_phase": markers.atdd_pure_phase,
                            "project_root": markers.project_root,
                        }
                    continue

                # Classic dispatch: first complete marker set wins.
                if classic_context is None and markers.project_id and markers.step_id:
                    classic_context = {
                        "project_id": markers.project_id,
                        "step_id": markers.step_id,
                        "project_root": markers.project_root,
                    }

    except (OSError, PermissionError) as e:
        _log_transcript_audit("HOOK_TRANSCRIPT_ERROR", transcript_path, error=str(e))
        return None

    # An atdd_pure dispatch takes precedence — it IS an atdd_pure return.
    if atdd_pure_context is not None:
        return atdd_pure_context
    if classic_context is not None:
        return classic_context

    _log_transcript_audit("HOOK_TRANSCRIPT_NO_MARKERS", transcript_path)
    return None


# ---------------------------------------------------------------------------
# DES context resolution (direct protocol vs transcript-based)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _AtddPureResolvedContext:
    """Resolved DES context for an atdd_pure dispatch return (T-C).

    Unlike the classic 5-tuple, an atdd_pure return carries NO
    execution_log_path and NO step_id -- atdd_pure is execution-log-free.
    The slice is identified by ``slice_id``; ``effective_cwd`` is retained for
    audit emission and future (T-G) trailer verification.
    """

    project_id: str
    slice_id: str | None
    atdd_pure_phase: str | None
    project_root_marker: str | None
    effective_cwd: str


@dataclass(frozen=True)
class _WaveOnlyResolvedContext:
    """Resolved DES context for a wave-only Agent()-dispatch return (WGO-001).

    The shape an ``Agent()``-dispatched wave-agent (e.g. a DESIGN architect)
    return carries: a ``DES-WAVE`` marker + a ``DES-PROJECT-ID`` marker, but NO
    classic execution-log step identifier and NO atdd_pure markers. Unlike the
    classic 5-tuple it carries NO execution_log_path and NO step_id -- wave-only
    is execution-log-free (like atdd_pure). It routes straight into
    ``SubagentStopService.validate`` so the EXISTING wave review-verdict gate-out
    (which runs at validate Step -1, before any execution-log read) fires. The
    feature_id comes from the marker (the floor carries no project_id).
    """

    declared_wave: str
    project_id: str
    effective_cwd: str
    # fix-floor-auto-close-cross-wave: the returning agent's subagent_type (the
    # Claude Code SubagentStop ``agent_type``). The owner identity the cross-wave
    # auto-close gates on -- threaded into SubagentStopContext so the close fires
    # on the LIVE hook path when WAVE_OWNERS[subagent_type] == active wave.
    subagent_type: str = ""


@dataclass(frozen=True)
class _WaveOnlyUnresolved:
    """A DES-WAVE-bearing return the wave-only resolver could not resolve (DDD-6).

    The fail-closed boundary (WGO-001 slice-06). A return whose transcript carries
    a ``DES-WAVE`` marker -- so it IS a DES return -- that the resolver cannot map
    to a governed wave context: the wave is OUT-OF-VOCABULARY, OR the
    ``DES-PROJECT-ID`` is absent. This is INDETERMINATE: a DES-WAVE was clearly
    declared but its context is unresolvable, which degrades LOUD to a refusal --
    NEVER the silent passthrough-allow.

    This is the THIRD outcome the resolver distinguishes, and it exists precisely
    to break the conflation the slice-06 ATs name: today the resolver returns
    ``None`` for BOTH "a DES-WAVE marker is present but unresolvable" AND "no
    DES-WAVE marker at all", and the caller maps ``None`` to the silent allow. A
    genuinely non-DES return (no ``DES-WAVE`` marker anywhere) still resolves to
    ``None`` and keeps the existing passthrough-allow (AT-15 byte-stable); only a
    marker-present-but-unresolvable return projects this fail-closed signal.

    ``reason`` names which unresolvability fired (out-of-vocab wave / missing
    project id) -- the LOUD half of the degrade, surfaced in the block body.
    """

    reason: str
    declared_wave: str | None
    project_id: str | None


def _resolve_des_context(
    hook_input: dict,
) -> (
    tuple[str, str, str, str | None, str]
    | _AtddPureResolvedContext
    | _WaveOnlyResolvedContext
    | _WaveOnlyUnresolved
    | tuple[None, dict, int]
):
    """Resolve DES context from hook input.

    Supports two protocols:
    1. Direct DES format (CLI testing): {"executionLogPath", "projectId", "stepId"}
    2. Claude Code protocol (live hooks): {"agent_transcript_path", "cwd", ...}

    Path-resolution priority for the Claude Code protocol:
      - validated DES-PROJECT-ROOT marker  >  hook_input["cwd"]  (fallback)

    Validation (project_root_validator): absolute path + exists + git work tree
    + git-common-dir matches fallback cwd. Invalid marker degrades to cwd.

    Returns:
        On success: (execution_log_path, project_id, step_id, project_root_marker,
                     effective_cwd)
            project_root_marker is the raw marker value when present (regardless
            of validation outcome), None otherwise. Used for audit-log emission.
            effective_cwd is the resolved working directory (validated marker
            value or hook_input cwd fallback). Used for git-trailer commit
            verification.
        On error/passthrough: (None, response_dict, exit_code)
    """
    execution_log_path = hook_input.get("executionLogPath")
    project_id = hook_input.get("projectId")
    step_id = hook_input.get("stepId")

    uses_direct_des_protocol = execution_log_path or project_id or step_id

    if uses_direct_des_protocol:
        if not (execution_log_path and project_id and step_id):
            return (
                None,
                {
                    "status": "error",
                    "reason": "Missing required fields: executionLogPath, projectId, and stepId are all required",
                },
                1,
            )
        if not Path(execution_log_path).is_absolute():
            return (
                None,
                {
                    "status": "error",
                    "reason": f"executionLogPath must be absolute (got: {execution_log_path})",
                },
                1,
            )
        # Direct DES protocol has no cwd / no marker — use empty effective_cwd
        return execution_log_path, project_id, step_id, None, ""

    # Claude Code protocol - extract DES context from transcript
    agent_transcript_path = hook_input.get("agent_transcript_path")
    cwd = hook_input.get("cwd", "")

    des_context = None
    if agent_transcript_path:
        des_context = extract_des_context_from_transcript(agent_transcript_path)

    if des_context is None:
        # WGO-001 wave-only reachability route (ADD-not-mutate): the classic +
        # atdd_pure extractor returned None for a return carrying NEITHER marker
        # set. Before the passthrough-allow, re-parse the transcript for a
        # wave-only Agent()-dispatch shape. Three outcomes (slice-06 DDD-6):
        #   * _WaveOnlyResolvedContext -- a DES-WAVE declaration (in the wave
        #     vocabulary) + a DES-PROJECT-ID: route it into validate so the
        #     EXISTING wave review-verdict gate-out fires.
        #   * _WaveOnlyUnresolved -- a DES-WAVE marker IS present but cannot be
        #     resolved (out-of-vocab wave / missing project id): degrade LOUD to
        #     a fail-closed refusal, NEVER the silent allow.
        #   * None -- NO DES-WAVE marker at all (a genuinely non-DES return):
        #     keep the existing passthrough-allow (byte-stable, AT-15).
        wave_only = _resolve_wave_only_context(
            agent_transcript_path, cwd, hook_input.get("agent_type") or ""
        )
        if wave_only is not None:
            return wave_only
        return None, {"decision": "allow"}, 0

    raw_marker = des_context.get("project_root")

    # atdd_pure dispatch (T-C): no execution-log to resolve. Marker-aware
    # effective cwd is still computed (for audit / future trailer checks),
    # but the resolved context carries an empty execution_log_path and
    # empty step_id -- the SubagentStop service keys on mode == "atdd_pure"
    # and skips ExecutionLogReader entirely.
    if des_context.get("mode") == "atdd_pure":
        project_id = des_context["project_id"]
        effective_cwd = cwd
        if raw_marker:
            validated = validate_project_root(raw_marker, cwd)
            if validated is not None:
                effective_cwd = str(validated)
        return _AtddPureResolvedContext(
            project_id=project_id,
            slice_id=des_context.get("slice_id"),
            atdd_pure_phase=des_context.get("atdd_pure_phase"),
            project_root_marker=raw_marker,
            effective_cwd=effective_cwd,
        )

    project_id = des_context["project_id"]
    step_id = des_context["step_id"]

    # Marker-aware effective cwd: validate marker → use; else fall back to cwd
    effective_cwd = cwd
    if raw_marker:
        validated = validate_project_root(raw_marker, cwd)
        if validated is not None:
            effective_cwd = str(validated)

    try:
        from pathlib import Path as _Path

        resolved = resolve_execution_log_path(
            project_id,
            cwd=_Path(effective_cwd),
        )
        execution_log_path = str(resolved)
    except (FileNotFoundError, ValueError) as exc:
        # No log found or ambiguous — fall back to deliver/ path so downstream
        # validation produces a meaningful "not found" error message.
        execution_log_path = os.path.join(
            effective_cwd,
            "docs",
            "feature",
            project_id,
            "deliver",
            "execution-log.json",
        )
        _ = exc  # error surfaced by SubagentStopService when log not found
    return execution_log_path, project_id, step_id, raw_marker, effective_cwd


def _resolve_wave_only_context(
    agent_transcript_path: str | None,
    cwd: str,
    subagent_type: str = "",
) -> _WaveOnlyResolvedContext | _WaveOnlyUnresolved | None:
    """Re-parse the transcript for a wave-only Agent()-dispatch shape (WGO-001).

    Three outcomes (slice-06 DDD-6 fail-closed boundary):

    * ``_WaveOnlyResolvedContext`` -- the transcript carries a DES-WAVE
      declaration whose value is in ``WAVE_VOCABULARY`` AND a DES-PROJECT-ID:
      the resolvable wave-only shape (routes into the gate-out, slice-01).
    * ``_WaveOnlyUnresolved`` -- a DES-WAVE marker IS present (the return IS a
      DES return) but its context cannot be resolved: the wave is
      OUT-OF-VOCABULARY, OR the DES-PROJECT-ID is absent. This is INDETERMINATE
      and degrades LOUD to a fail-closed refusal -- NEVER the silent
      passthrough-allow. The conflation slice-06 cures: at HEAD this case
      returned ``None`` and the caller mapped it to the silent allow.
    * ``None`` -- NO DES-WAVE marker anywhere (a genuinely non-DES return): the
      caller keeps the existing passthrough-allow (byte-stable, AT-15).

    Uses the EXISTING ``DesMarkerParser`` -- no parser change. The
    ``effective_cwd`` follows the same marker-aware resolution as the
    classic/atdd_pure paths.
    """
    if not agent_transcript_path:
        return None

    saw_des_wave_marker = False
    declared_wave: str | None = None
    project_id: str | None = None
    raw_marker: str | None = None
    for entry in _read_transcript_entries(agent_transcript_path):
        message = entry.get("message", {})
        if not isinstance(message, dict):
            continue
        # FR-5: a wave-only self-declaration is something THIS agent EMITS (an
        # assistant message), not user-injected context. A skill's DES-WAVE
        # marker shown as copy-paste GUIDANCE for a FUTURE dispatch is prose,
        # not a directive; scanning user-role messages false-positives on that
        # documentation and emits a spurious WAVE_GATEOUT_INDETERMINATE for an
        # agent that never dispatched. Scope the scan to the agent's own
        # (assistant) messages.
        if message.get("role") != "assistant":
            continue
        content = _normalize_message_content(message.get("content", ""))
        # FR-5 parity with extract_des_context_from_transcript (the C8 guard):
        # strip fenced/quoted regions before the marker match so a fenced
        # example marker reads as documentation, not a directive.
        content = _strip_fenced_regions(content)
        if "DES-WAVE" not in content:
            continue
        saw_des_wave_marker = True
        markers = DesMarkerParser().parse(content)
        if markers.declared_wave is not None:
            declared_wave = markers.declared_wave
        if markers.project_id is not None:
            project_id = markers.project_id
        if markers.project_root is not None:
            raw_marker = markers.project_root

    if declared_wave not in WAVE_VOCABULARY or not project_id:
        # A DES-WAVE marker was present but the context is unresolvable
        # (out-of-vocab wave / missing project id) -> degrade LOUD (DDD-6). A
        # transcript with NO DES-WAVE marker at all stays a genuine non-DES
        # return -> None -> the caller's byte-stable passthrough-allow (AT-15).
        if not saw_des_wave_marker:
            return None
        if declared_wave not in WAVE_VOCABULARY:
            reason = (
                f"out-of-vocabulary wave {declared_wave!r}: a DES-WAVE marker was "
                f"declared but is not a governed wave {sorted(WAVE_VOCABULARY)}"
            )
        else:
            reason = (
                f"missing project identity: a governed DES-WAVE ({declared_wave!r}) "
                "was declared but no DES-PROJECT-ID accompanies it"
            )
        return _WaveOnlyUnresolved(
            reason=reason,
            declared_wave=declared_wave,
            project_id=project_id,
        )

    effective_cwd = cwd
    if raw_marker:
        validated = validate_project_root(raw_marker, cwd)
        if validated is not None:
            effective_cwd = str(validated)
    return _WaveOnlyResolvedContext(
        declared_wave=declared_wave,
        project_id=project_id,
        effective_cwd=effective_cwd,
        subagent_type=subagent_type,
    )


def _build_block_notification(
    project_id: str, step_id: str, execution_log_path: str, decision
) -> dict:
    """Build protocol response for a blocked subagent stop decision."""
    reason = decision.reason or "Validation failed"

    recovery_suggestions = decision.recovery_suggestions or []
    recovery_steps = "\n".join(
        [f"  {i + 1}. {s}" for i, s in enumerate(recovery_suggestions)]
    )

    notification = f"""STOP HOOK VALIDATION FAILED

Step: {project_id}/{step_id}
Execution Log: {execution_log_path}
Status: FAILED
Error: {reason}

RECOVERY REQUIRED:
{recovery_steps}

The step validation failed. You MUST fix these issues before proceeding.

IMPORTANT: Only the executing agent may write to execution-log.json.
The orchestrator must RE-DISPATCH the agent to execute missing phases.
Never write log entries for phases that were not actually executed."""

    return {
        "decision": "block",
        "reason": notification,
    }


def _read_transcript_entries(transcript_path: str) -> list[dict]:
    """Parse a transcript JSONL file into a list of dict entries.

    Fail-open: malformed lines are skipped silently. Missing file yields
    empty list. Never raises.
    """
    path = Path(transcript_path)
    if not path.exists():
        return []
    entries: list[dict] = []
    try:
        with open(path) as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    entry = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if isinstance(entry, dict):
                    entries.append(entry)
    except (OSError, PermissionError):
        return []
    return entries


def _emit_token_usage_events(
    transcript_path: str | None,
    *,
    agent_name: str | None,
    feature_id: str | None = None,
    wave: str | None = None,
) -> None:
    """Read transcript, extract token-usage events, write each via the audit port.

    Per D4 (fail-open): any failure inside this routine is swallowed so
    the SubagentStop hook itself is never blocked by token instrumentation.
    """
    if not transcript_path:
        return
    try:
        entries = _read_transcript_entries(transcript_path)
        events = extract_token_usage_events(
            entries,
            agent_name=agent_name or "unknown",
            feature_id=feature_id,
            wave=wave,
        )
        if not events:
            return
        writer = hook_protocol.get_audit_writer()
        for event in events:
            writer.log_event(_to_audit_event(event))
    except Exception:
        # Fail-open: token instrumentation must never block the hook.
        pass


def _to_audit_event(event: AgentUsageObservedEvent) -> AuditEvent:
    """Convert a domain event to the port-level AuditEvent for logging."""
    return AuditEvent(
        event_type=EventType.AGENT_USAGE_OBSERVED.value,
        timestamp=event.timestamp or SystemTimeProvider().now_utc().isoformat(),
        feature_name=event.feature_id,
        data=event.to_audit_data(),
    )


def _extract_execution_stats(hook_input: dict) -> tuple[int | None, int | None]:
    """Extract turns_used and tokens_used from hook input.

    Claude Code may include num_turns and total_tokens in SubagentStop hook_input.

    Args:
        hook_input: Parsed JSON from stdin.

    Returns:
        Tuple of (turns_used, tokens_used), each None if not present.
    """
    turns_used: int | None = None
    tokens_used: int | None = None
    raw_turns = hook_input.get("num_turns")
    raw_tokens = hook_input.get("total_tokens")
    if raw_turns is not None:
        turns_used = int(raw_turns)
    if raw_tokens is not None:
        tokens_used = int(raw_tokens)
    return turns_used, tokens_used


# ---------------------------------------------------------------------------
# atdd_pure gate-intercept shared helpers (U2/U4 -- slice-02/slice-04)
# ---------------------------------------------------------------------------

# Each spine gate CLI is a pure-function / pytest-collection invocation; the
# explicit subprocess timeout is the ADR-030 D5 fail-stuck discipline -- a
# timeout or signal-kill is treated identically to a non-zero exit (block).
# U2 (G_COMMIT) gates are fast; the U4 feature-end walking-skeleton e2e needs a
# wider budget.
G_COMMIT_GATE_SUBPROCESS_TIMEOUT_SECONDS = 120
FEATURE_END_GATE_SUBPROCESS_TIMEOUT_SECONDS = 300

# The per-slice commit exit-gate (U2) and the feature-end terminal gate (U4)
# route a returning atdd_pure agent by the phase word it carries. Both routing
# subsets are imported from the phase-identity SSOT (``atdd_pure_phases``):
# ``_COMMIT_GATE_PHASES`` (canonical D_REFACTOR_COMMIT + legacy G_COMMIT replay)
# and ``_FEATURE_END_RETURN_PHASE`` (the F_FINAL_REVIEW reviewer return). They
# are no longer restated as bare literals here — single-sourced in the enum
# module so a vocabulary change propagates once.


def _run_gate_subprocess(
    module: str, args: list[str], repo: Path, timeout_seconds: int
) -> int:
    """Run a spine gate CLI as a subprocess; return its exit code.

    A timeout or signal-kill is mapped to a non-zero exit (block) per the
    ADR-030 D5 fail-stuck discipline. The single subprocess-invocation helper
    the U2 G_COMMIT gates and the U4 feature-end gate both delegate to.
    """
    completed = des_spawn(
        None,
        module,
        *args,
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    return completed.returncode


def _emit_atdd_pure_block(reason: str, event: str, **extra: object) -> int:
    """Print a `{decision:block}` body and return exit 0 (handler block protocol).

    SubagentStop blocks via `{"decision":"block"}` + exit 0 -- exit 2 makes
    Claude Code ignore stdout, and a bare exit 1 is an *error* (no decision
    body), which for an atdd_pure branch is fail-OPEN. Always exit 0 here.

    The single block-emission helper the U2 G_COMMIT and U4 feature-end
    intercepts both delegate to.
    """
    payload: dict[str, object] = {"decision": "block", "reason": reason, "event": event}
    payload.update(extra)
    print(json.dumps(payload))
    return 0


# The bounded-block terminal bound (oss-spine-watchdog slice-02, RCA root #68):
# terminate ON the Nth identical block, so N-1 priors precede the terminating
# invocation. N=3 (DISCUSS D-4 / DESIGN OQ-3).
_BOUNDED_BLOCK_N = 3


# ---------------------------------------------------------------------------
# Watchdog terminal-event vocabulary -- ONE SSOT (oss-spine-watchdog R-69-E)
# ---------------------------------------------------------------------------
#
# The four genuine watchdog terminal-event names live here as named constants
# so they are defined ONCE. Before R-69-E they recurred as raw string literals
# at every emit site AND inside the `_EXISTING_TERMINAL_EVENTS` recognized set;
# the D1 drift root (RCA #68 class) is precisely "a new terminal added at an
# emit site but forgotten in the recognized set". Single-sourcing the vocabulary
# makes that drift structurally impossible: a new terminal adds ONE constant and
# the emit + recognition both reference it.
#
# Runtime values are byte-identical to the prior literals (ledger records + AT
# assertions depend on the exact strings, e.g. composition_slice_04.py pins
# {SliceCommitBlockedTerminal, StaleAgentClosed, CollectionCrashTerminal}) --
# this is a literal->named-constant extraction, NOT a value change.
#
# The three WATCHDOG-EMITTED terminals (each routed through
# `_emit_terminating_indeterminate`):
_EVENT_SLICE_COMMIT_BLOCKED_TERMINAL = "SliceCommitBlockedTerminal"
_EVENT_STALE_AGENT_CLOSED = "StaleAgentClosed"
_EVENT_COLLECTION_CRASH_TERMINAL = "CollectionCrashTerminal"
# The completed terminal emitted at the G_COMMIT gate boundary (a member of the
# no-double-close recognized set, but NOT routed through the watchdog terminal
# helper -- it is the verified-commit success record):
_EVENT_SLICE_COMMIT_VERIFIED = "SliceCommitVerified"


def _emit_terminating_indeterminate(
    project_id: str,
    effective_cwd: str,
    slice_id: str | None,
    event_name: str,
    reason_message: str,
) -> None:
    """The ONE shared terminating-INDETERMINATE shape for every watchdog terminal.

    oss-spine-watchdog slice-04 (terminal-coherence feature-end-fix): the deep
    feature-end review (`a360758f`) rejected the coherent feature because the
    DDD-5 terminating-INDETERMINATE wire-format was realized INCONSISTENTLY
    across the 3 terminals (collection-crash, bounded-block, stale). This helper
    is the single SSOT every terminal routes through. It drives the sinks of a
    DDD-5 terminal:

      (a) a DURABLE ledger record (`{"event": event_name, "slice_id": ...}`)
          appended via the production `AtCompletionLedger` writer -- the durable
          half of "loud", read post-mortem by a not-watching operator; this is
          the KPI SSOT until the DV-2 audit-KPI sink is wired;
      (b) a LOUD `sys.__stderr__` warning that NAMES the terminal (the operator
          reading the live stream learns WHY the agent terminated); and
      (c) the DV-2 WATCHDOG_* audit KPI event -- NOT wired at this boundary yet,
          left as the R-69-C residue below (do NOT fabricate a sink -- that
          would be theater; the durable ledger record is the KPI SSOT for now).

    The durable-record write is FAIL-OPEN (mirror `_emit_g_commit_ledger_event`):
    a ledger-write failure must NOT change the terminal decision. The terminal
    decision (non-block, exit 0) is owned by the CALLER -- this helper only emits
    the terminal's durable+loud shape; it never decides whether to terminate. The
    fail-safe DIRECTIONS of the callers are UNCHANGED by this unification:
    slice-02 fails-closed-to-block, slice-03 fails-open-to-leave-alone.
    """
    if slice_id:
        try:
            from des.adapters.driven.logging.at_completion_ledger import (
                AtCompletionLedger,
            )

            ledger = AtCompletionLedger(project_id, Path(effective_cwd or "."))
            ledger._append_record({"event": event_name, "slice_id": slice_id})
        except Exception:
            # Fail-open: the terminal decision already stands; ledger emission is
            # audit (mirror `_emit_g_commit_ledger_event`).
            pass
    # TODO(R-69-C): DV-2 WATCHDOG_* audit-log dual-emit. The audit-KPI sink is
    # not wired at the real-hook boundary yet; the durable ledger record above is
    # the KPI SSOT until R-69-C lands. Do NOT fabricate a sink here.
    print(reason_message, file=sys.__stderr__)


def _emit_bounded_block_terminal(
    resolved: _AtddPureResolvedContext, block_reason: str
) -> int:
    """Emit the terminating INDETERMINATE for a bounded-block terminal (slice-02).

    The Nth identical `(slice_id, pinned_commit_sha, block_reason)` exit-gate
    block terminates the re-fire loop (RCA #68) instead of re-emitting another
    `{decision:block}`. The terminal is:

      * NON-block -- NO `{"decision":"block"}` body on stdout, so Claude Code
        reaches a terminal Stop rather than re-firing the agent forever; and
      * LOUD + DURABLE -- routed through the shared
        `_emit_terminating_indeterminate` (slice-04 coherence fix): a durable
        `SliceCommitBlockedTerminal` ledger record (DDD-5 / DV-1; KPI-2 "the 3rd
        block paired with a terminal record") PLUS a `sys.__stderr__` warning
        that NAMES the bound, never a silent allow.

    Always exit 0 (the SubagentStop protocol: a non-zero exit would invert the
    contract and red CI -- the terminal is loud via stderr + durable record,
    never via exit code).
    """
    slice_id = resolved.slice_id
    _emit_terminating_indeterminate(
        resolved.project_id,
        resolved.effective_cwd,
        slice_id,
        _EVENT_SLICE_COMMIT_BLOCKED_TERMINAL,
        f"INDETERMINATE: bounded-block terminal -- {_BOUNDED_BLOCK_N} identical "
        f"exit-gate blocks for (slice={slice_id}, pinned commit, reason="
        f"{block_reason}); terminating the agent to break the re-fire loop "
        f"(no progress across {_BOUNDED_BLOCK_N} attempts).",
    )
    return 0


def _prior_identical_block_count(
    resolved: _AtddPureResolvedContext, pinned_sha: str, block_reason: str
) -> int:
    """Count prior identical `SliceCommitBlocked` records (fail-closed to block).

    Reads `count_slice_commit_blocked` from the SAME ledger the block emission
    writes (same `(project_id, effective_cwd)` construction), so the count sees
    the prior identical-key blocks. Fail-closed: if the slice is unidentified or
    the ledger read raises (a corrupt / unreadable ledger -- M7 raises rather
    than undercounting), return -1 so the caller takes the existing
    `{decision:block}` path. The bounded-block terminal must NEVER fire on a
    count-read error -- terminating-on-error would kill a legitimate agent.
    """
    if not resolved.slice_id:
        return -1
    try:
        from des.adapters.driven.logging.at_completion_ledger import (
            AtCompletionLedger,
        )

        ledger = AtCompletionLedger(
            resolved.project_id, Path(resolved.effective_cwd or ".")
        )
        return ledger.count_slice_commit_blocked(
            resolved.slice_id, pinned_sha, block_reason
        )
    except Exception:
        # Fail-closed: degrade to the existing block, never terminate on error.
        return -1


# ---------------------------------------------------------------------------
# U2 — G_COMMIT exit-gate SubagentStop intercept (slice-02 / ADR-030 D2)
# ---------------------------------------------------------------------------


def _resolve_head_sha(repo: Path) -> str:
    """Resolve ``git rev-parse HEAD`` once, in ``repo`` (M9 SHA-pinning).

    The G_COMMIT exit gates run against this pinned SHA rather than a moving
    ``HEAD`` reference -- under a concurrent amend/rebase the ``HEAD`` U2
    resolved can move before the gates inspect it; pinning makes the verdict
    deterministic against one commit.
    """
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
        timeout=G_COMMIT_GATE_SUBPROCESS_TIMEOUT_SECONDS,
    )
    return completed.stdout.strip()


def _emit_g_commit_ledger_event(
    resolved: _AtddPureResolvedContext,
    event: str,
    *,
    pinned_commit_sha: str | None = None,
    block_reason: str | None = None,
) -> None:
    """Emit a SliceCommitVerified / SliceCommitBlocked record into the U3 ledger.

    Consumes the slice-03 `AtCompletionLedger.append_gate_event` API as-is for
    the verified record. For a `SliceCommitBlocked` record the bounded-block
    terminal (oss-spine-watchdog slice-02) threads the resolved `pinned_commit_sha`
    AND the `block_reason` as extra fields so the bounded-block count
    (`count_slice_commit_blocked`) can match identical-key priors -- the
    `verdict_hash` precedent (extra fields are hashed into `record_hash`, M7).
    A `SliceCommitVerified` emission threads neither, so its record is byte-
    equivalent to before.

    Fail-open on the audit emission itself -- a ledger write failure must not
    change the gate verdict.
    """
    if not resolved.slice_id:
        return
    try:
        from des.adapters.driven.logging.at_completion_ledger import (
            AtCompletionLedger,
        )

        ledger = AtCompletionLedger(
            resolved.project_id, Path(resolved.effective_cwd or ".")
        )
        if pinned_commit_sha is None and block_reason is None:
            ledger.append_gate_event(event=event, slice_id=resolved.slice_id)
            return
        fields: dict[str, object] = {
            "event": event,
            "slice_id": resolved.slice_id,
        }
        if pinned_commit_sha is not None:
            fields["pinned_commit_sha"] = pinned_commit_sha
        if block_reason is not None:
            fields["block_reason"] = block_reason
        ledger._append_record(fields)
    except Exception:
        # Fail-open: the gate verdict already stands; ledger emission is audit.
        pass


def _emit_g_commit_phase_completed(resolved: _AtddPureResolvedContext) -> None:
    """Emit the symmetric `WorkflowPhaseCompletedGCommit` DELIVER-exit terminal.

    slice-02 (oss-hook-side-phase-injection): a verified slice commit now leaves
    BOTH a `SliceCommitVerified` (the existing gate-boundary record) AND a
    `WorkflowPhaseCompletedGCommit` success terminal (SF ADR-016 symmetry, the
    DELIVER-exit mirror of slice-01's DISTILL-exit `WorkflowPhaseCompletedDistill`).
    Additive -- it never replaces `SliceCommitVerified`.

    Fail-open on the audit emission itself -- a ledger-write failure must not
    change the gate verdict (mirror of `_emit_g_commit_ledger_event`).
    """
    if not resolved.slice_id:
        return
    try:
        from des.adapters.driven.logging.at_completion_ledger import (
            AtCompletionLedger,
        )

        ledger = AtCompletionLedger(
            resolved.project_id, Path(resolved.effective_cwd or ".")
        )
        ledger.append_workflow_phase_completed_g_commit(resolved.slice_id)
    except Exception:
        # Fail-open: the gate verdict already stands; ledger emission is audit.
        pass


# ---------------------------------------------------------------------------
# Stale-agent timeout terminal (oss-spine-watchdog slice-03, #68 P2-E)
# ---------------------------------------------------------------------------

# The DESIGN OQ-4 default stale threshold = 20 minutes.
# TODO(R1): read stale threshold from control-plane config (.nwave/config.yaml).
# R1's config-SSOT stale-threshold surface does not exist yet (confirmed
# 2026-06-04: `.nwave/config.yaml` exposes only workflow/atdd_pure/gate keys);
# until R1 lands it, the default is hard-coded here -- the threshold source is a
# DELIVER seam decision, not a re-solve of config SSOT in this slice.
_STALE_THRESHOLD_MINUTES = 20

# The terminal events that mean "this agent already reached a GENUINE terminal
# state" -- the no-double-close precondition (DESIGN OQ-4): a stale agent is
# closed ONLY when NO genuine terminal record exists for its (feature_id,
# slice_id).
#
# slice-04 (terminal-coherence feature-end-fix, BLOCKER-3 / R-69-B): this set is
# re-keyed onto GENUINE terminals only. The non-terminal `SliceCommitBlocked` is
# DROPPED -- it is the re-fire record a bounded-block-terminated agent leaves
# behind (2 precede every bounded-block terminal), NOT a terminal; keeping it
# made the stale check mistake a historical re-fire block for a terminal and
# WRONGLY leave a genuinely-stuck agent to hang (the silent-hang false-negative).
# The now-durable `SliceCommitBlockedTerminal` (the bounded-block terminal's
# durable record) and `StaleAgentClosed` (this very stale check's own terminal)
# are ADDED. `SliceCommitVerified` (the completed terminal) is unchanged -- the
# AT-03 anti-vacuity pin stays green.
# slice-05: CollectionCrashTerminal is a genuine terminal; the no-double-close
# stale-check must recognize it (same coherence class as slice-04 BLOCKER-3) --
# otherwise a later stale-phase invocation on an already-collection-terminated
# slice would emit a redundant StaleAgentClosed.
_EXISTING_TERMINAL_EVENTS = frozenset(
    {
        _EVENT_SLICE_COMMIT_VERIFIED,
        _EVENT_SLICE_COMMIT_BLOCKED_TERMINAL,
        _EVENT_STALE_AGENT_CLOSED,
        _EVENT_COLLECTION_CRASH_TERMINAL,
    }
)


def _maybe_emit_stale_agent_closed(resolved: _AtddPureResolvedContext) -> bool:
    """Close a returning atdd_pure agent gone stale past the timeout (slice-03).

    On a returning atdd_pure agent the wall-clock gap between the agent's LAST
    PROGRESS SIGNAL -- the AT-completion ledger's MOST-RECENT record `timestamp`
    for this `(feature_id, slice_id)` (the contract SSOT, DESIGN OQ-4 / R-7) --
    and now is computed. The agent is closed iff:

      * the gap EXCEEDS the threshold (DESIGN OQ-4 default 20 min), AND
      * NO `completed`/`blocked` terminal record exists for the key (the
        no-double-close precondition -- an already-terminal agent is left alone
        even when its progress gap is stale).

    When both hold, emit `StaleAgentClosed` -- a TERMINATING INDETERMINATE: a
    durable `StaleAgentClosed` ledger record (the durable half of "loud", read
    post-mortem by a not-watching operator) PLUS a loud `sys.__stderr__` warning
    that NAMES the staleness (mirror of `_emit_bounded_block_terminal`). The
    caller then returns exit 0 with NO `{decision:block}` body (DESIGN OQ-5 / D-3:
    the terminal is loud via stderr + ledger, NEVER a non-zero exit). Returns
    True so the caller takes the terminal path; False so the caller takes the
    existing normal `service.validate` return UNCHANGED.

    FAIL-SAFE direction (the catastrophic-failure guard): a ledger-read error /
    corrupt ledger / missing-field / unparseable-timestamp / unidentified slice
    MUST degrade to the NORMAL return (leave the agent alone) -- NEVER close on
    error. Closing a legitimately-working agent because of a read error is the
    catastrophic failure mode (worse than failing to close a stale one). So the
    whole check is wrapped fail-open: on ANY exception OR ambiguity, return False
    and let the existing allow stand. (This INVERTS slice-02's
    `_prior_identical_block_count`, which fails-closed-to-block because there the
    protected property is "don't pass a bad verdict"; HERE the protected property
    is "don't kill a working agent".)
    """
    if not resolved.slice_id:
        return False
    try:
        from datetime import datetime, timezone

        from des.adapters.driven.logging.at_completion_ledger import (
            AtCompletionLedger,
        )

        ledger = AtCompletionLedger(
            resolved.project_id, Path(resolved.effective_cwd or ".")
        )
        records = [
            record
            for record in ledger.read_records()
            if record.get("slice_id") == resolved.slice_id
        ]
        if not records:
            # No progress signal at all -- nothing to age out; leave alone.
            return False
        if any(record.get("event") in _EXISTING_TERMINAL_EVENTS for record in records):
            # No-double-close precondition: an already-terminal agent is left
            # alone even when its progress gap is stale (AT-03).
            return False

        last_progress = records[-1].get("timestamp")
        if not isinstance(last_progress, str) or not last_progress:
            return False
        moment = datetime.fromisoformat(last_progress.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        gap_minutes = (now - moment).total_seconds() / 60.0
        if gap_minutes <= _STALE_THRESHOLD_MINUTES:
            # Fresh progress within the threshold -- the agent is working (AT-02).
            return False

        # slice-04 coherence fix: route the stale-agent terminal through the SAME
        # shared `_emit_terminating_indeterminate` the bounded-block terminal uses
        # (durable `StaleAgentClosed` record + loud stderr + the R-69-C DV-2
        # residue) so all 3 watchdog terminals share one DDD-5 emission SSOT.
        # Behavior-preserving: the durable record + loud stderr are identical to
        # the prior inline emission; the FAIL-OPEN-to-leave-alone direction of
        # this caller is UNCHANGED (the close decision is owned HERE, above).
        _emit_terminating_indeterminate(
            resolved.project_id,
            resolved.effective_cwd,
            resolved.slice_id,
            _EVENT_STALE_AGENT_CLOSED,
            f"INDETERMINATE: stale-agent terminal -- the returning agent's last "
            f"progress for (slice={resolved.slice_id}) is "
            f"{gap_minutes:.0f} minutes old, past the {_STALE_THRESHOLD_MINUTES}-"
            f"minute stale threshold, with no completed/blocked terminal on record; "
            f"closing the agent (StaleAgentClosed) to break the silent hang instead "
            f"of leaving it to wait on a never-arriving notification.",
        )
        return True
    except Exception:
        # FAIL-SAFE: leave the agent alone on ANY error -- never close a possibly
        # working agent because of a ledger-read / parse failure.
        return False


def _handle_g_commit_exit_gate(
    resolved: _AtddPureResolvedContext,
    hook_input: dict[str, object],
    hook_id: str,
) -> int:
    """Run the U2 G_COMMIT exit gate for a returning atdd_pure crafter.

    Runs the slice-commit completeness gate (E1) and the contract gate (E2)
    against a pinned ``HEAD`` SHA. On either failure the orchestrator is
    blocked via `{"decision":"block"}` + exit 0; a verified commit is allowed.
    The whole branch body is wrapped in a try/except (M1): any exception is an
    `AtddPureHookInternalError` block + exit 0, never the bare exit-1 path.

    F-07: a multi-`Slice-Id` batched commit is accepted -- U2 adds no
    commit-scope logic, it delegates to `verify_slice_commit_completeness`,
    whose E1 verdict already verifies every listed slice.
    """
    try:
        # M1 test seam: an injected fault exercises the fail-closed except path.
        if os.environ.get("NWAVE_U2_FORCE_HANDLER_FAULT") == "1":
            raise RuntimeError("injected G_COMMIT intercept fault")

        repo = Path(resolved.effective_cwd or hook_input.get("cwd", "") or ".")

        log_hook_invoked(
            "subagent_stop_g_commit_intercept",
            {
                "mode": "atdd_pure",
                "project_id": resolved.project_id,
                "slice_id": resolved.slice_id,
                "atdd_pure_phase": resolved.atdd_pure_phase,
            },
            hook_id=hook_id,
        )

        pinned_sha = _resolve_head_sha(repo)

        # slice-06 test seam (R-69-F): force a real `subprocess.TimeoutExpired`
        # from inside the gate try-block AFTER `pinned_sha` is resolved, so the
        # REAL `except subprocess.TimeoutExpired` branch fires deterministically
        # and fast (a real 120s timeout against
        # `G_COMMIT_GATE_SUBPROCESS_TIMEOUT_SECONDS` is infeasible in tests and the
        # constant has no override). Sibling of the `NWAVE_U2_FORCE_HANDLER_FAULT`
        # seam at the top of this try -- env-gated, default off in production.
        if os.environ.get("NWAVE_U2_FORCE_GATE_TIMEOUT") == "1":
            raise subprocess.TimeoutExpired(
                cmd="des.cli.run_contract_gate",
                timeout=G_COMMIT_GATE_SUBPROCESS_TIMEOUT_SECONDS,
            )

        # slice-05 (BLOCKER-1, R-69-D): wire slice-01's collection precheck INTO
        # the gate BEFORE E2. A real collection crash on the committed contract
        # suite makes `run_contract_gate --collect-only` abort (exit 2 -- the #68
        # root). When that happens, TERMINATE via the slice-04 shared
        # `_emit_terminating_indeterminate` (durable terminal record + loud stderr
        # + non-block), short-circuiting BEFORE E2 so the crash does NOT flow into
        # the `{decision:block}` re-fire branch the harness loops on. The precheck
        # runs no-skip (D-7): `_run_gate_subprocess` forwards the handler's own
        # env, which carries NO `NWAVE_FRESHNESS=skip`, so collection runs on the
        # real installed tree. This is the contract-suite collection concern
        # (concern 2), DISTINCT from the install-freshness gate (concern 1) -- no
        # new freshness path is introduced. Fail-safe direction: terminate ONLY on
        # the clean exit-2 collection-crash signal; any other code (clean collect 0,
        # ordinary failure 1) proceeds to E1/E2 unchanged, so a working agent is
        # never spuriously collection-terminated (AT-03 discriminator). A timeout
        # raises and is caught by the outer handler -> fail-toward-block.
        precheck_code = _run_gate_subprocess(
            "des.cli.run_contract_gate",
            ["--repo", str(repo), "--collect-only"],
            repo,
            G_COMMIT_GATE_SUBPROCESS_TIMEOUT_SECONDS,
        )
        if precheck_code == 2:
            slice_id = resolved.slice_id
            _emit_terminating_indeterminate(
                resolved.project_id,
                resolved.effective_cwd,
                slice_id,
                _EVENT_COLLECTION_CRASH_TERMINAL,
                f"INDETERMINATE: collection-crash terminal -- the committed "
                f"contract suite for slice={slice_id} crashes on collection "
                f"(run_contract_gate --collect-only exit 2); terminating the agent "
                f"to break the re-fire loop instead of re-firing on a phantom hang "
                f"the walking skeleton exists to kill.",
            )
            return 0

        # M9 / F3: the pinned SHA is passed BOTH as `--commit` (the commit to
        # inspect) and `--expected-head` (the SHA to race-check against). Each
        # CLI re-reads HEAD and fails closed `CommitHeadRaced` if HEAD has moved
        # off the pinned SHA during the exit gate (a concurrent amend/rebase).
        # slice-03 (Seam A): scope E1's `.feature` completeness scan to the
        # committing feature via `--scope-feature-id`, so a co-resident feature
        # sharing this slice number on the tree is not cross-bound into this
        # commit's check. `--scope-feature-id` keeps the legacy E1-only verdict
        # shape and writes NO ledger record -- the hook stays the sole author of
        # the SliceCommitVerified record below (E1 runs once, one record). This
        # is deliberately NOT `--feature-id`, which would flip E1 into the
        # verify-then-record seam (a second contract run + a duplicate record).
        e1_code = _run_gate_subprocess(
            "des.cli.verify_slice_commit_completeness",
            [
                "--repo",
                str(repo),
                "--commit",
                pinned_sha,
                "--expected-head",
                pinned_sha,
                "--scope-feature-id",
                resolved.project_id,
            ],
            repo,
            G_COMMIT_GATE_SUBPROCESS_TIMEOUT_SECONDS,
        )
        e2_code = _run_gate_subprocess(
            "des.cli.run_contract_gate",
            [
                "--repo",
                str(repo),
                "--commit",
                pinned_sha,
                "--verify-gate-scope",
                "--expected-head",
                pinned_sha,
            ],
            repo,
            G_COMMIT_GATE_SUBPROCESS_TIMEOUT_SECONDS,
        )

        if e1_code == 0 and e2_code == 0:
            _emit_g_commit_ledger_event(resolved, _EVENT_SLICE_COMMIT_VERIFIED)
            # slice-02: leave the symmetric DELIVER-exit success terminal
            # ALONGSIDE SliceCommitVerified (SF ADR-016 symmetry, additive).
            _emit_g_commit_phase_completed(resolved)
            return 0

        failed = "slice-commit-completeness" if e1_code != 0 else "contract-gate"

        # slice-02 bounded-block terminal (RCA #68): before re-emitting the
        # block, count prior identical `(slice, pinned_sha, reason)` blocks. On
        # the Nth identical block (count of priors == N-1) terminate the agent
        # loud (a non-block INDETERMINATE) instead of re-firing it forever. A
        # new SHA or a different reason RESETS the count (D-4). The count read is
        # fail-closed: any read error degrades to the existing block (NEVER
        # terminate on a count-read error -- that would kill a legitimate agent).
        if (
            _prior_identical_block_count(resolved, pinned_sha, failed)
            == _BOUNDED_BLOCK_N - 1
        ):
            return _emit_bounded_block_terminal(resolved, failed)

        _emit_g_commit_ledger_event(
            resolved,
            "SliceCommitBlocked",
            pinned_commit_sha=pinned_sha,
            block_reason=failed,
        )
        return _emit_atdd_pure_block(
            f"G_COMMIT exit gate rejected {resolved.slice_id}: "
            f"{failed} gate failed (e1={e1_code}, e2={e2_code})",
            "SliceCommitBlocked",
        )
    except subprocess.TimeoutExpired as exc:
        # slice-06 (R-69-F): a gate-subprocess timeout is a COUNTABLE block, keyed
        # on `(slice, pinned_sha, "gate-timeout")` -- mirror the normal block path
        # above so a timeout-driven re-fire loop on the SAME commit terminates at
        # N=3 like any other block (instead of looping unbounded because the prior
        # fieldless emit could never match the count key). `pinned_sha` is resolved
        # before any gate subprocess runs, so it is in scope here. "gate-timeout"
        # is a distinct reason from "contract-gate"/"slice-commit-completeness", so
        # timeout blocks form their own count bucket. The count read fails closed to
        # block on error (never terminate on a count-read error).
        if (
            _prior_identical_block_count(resolved, pinned_sha, "gate-timeout")
            == _BOUNDED_BLOCK_N - 1
        ):
            return _emit_bounded_block_terminal(resolved, "gate-timeout")

        _emit_g_commit_ledger_event(
            resolved,
            "SliceCommitBlocked",
            pinned_commit_sha=pinned_sha,
            block_reason="gate-timeout",
        )
        return _emit_atdd_pure_block(
            f"G_COMMIT exit-gate invocation timed out: {exc}",
            "GateInvocationTimeout",
        )
    except Exception as exc:
        # M1 fail-closed: an atdd_pure-branch exception is a block, never the
        # generic bare-exit-1 path (which carries no decision body).
        return _emit_atdd_pure_block(
            f"G_COMMIT exit-gate handler error: {exc}",
            "AtddPureHookInternalError",
        )


# ---------------------------------------------------------------------------
# U4 — feature-end terminal SubagentStop intercept (slice-04 / ADR-030 D4)
# ---------------------------------------------------------------------------

# The closed status vocabulary of the markdown `[REF] Slice Plan` `Status`
# column (M12 fail-closed parse contract).
_SLICE_PLAN_STATUS_VOCABULARY = frozenset({"pending", "shipped"})


class _SlicePlanParseUnresolved(Exception):
    """Raised when the markdown slice-plan `Status` column fails M12 parsing."""


def _parse_slice_plan_rows(repo: Path, feature_id: str) -> list[tuple[str, str]]:
    """Parse the feature-delta `[REF] Slice Plan` into ``(slice_id, status)`` rows.

    Delegates to the ONE tolerant slice-plan parser shared with the carpaccio
    CLI entry gate (``des.cli.carpaccio_format.parse_slice_plan_rows``) so the
    entry gate and this exit gate parse the SAME plan identically -- no
    two-parser divergence (C10). Tolerant of an H2-H4 heading, a GFM-escaped
    ``\\|`` in a cell, and a 3- or 5-column table.

    Raises ``FileNotFoundError`` when the feature-delta is absent;
    ``_SlicePlanParseUnresolved`` when no slice-plan table is found.
    """
    from des.cli import carpaccio_format

    text = _feature_delta_path(repo, feature_id).read_text(encoding="utf-8")
    try:
        parsed_rows = carpaccio_format.parse_slice_plan_rows(text)
    except carpaccio_format.GateError as exc:
        raise _SlicePlanParseUnresolved(str(exc)) from exc
    return [(row.slice_id, row.status) for row in parsed_rows]


def _slice_plan_slice_ids(repo: Path, feature_id: str) -> frozenset[str]:
    """The set of slice ids declared in the feature-delta `[REF] Slice Plan`.

    Reused as the denominator of the "all slices shipped" check -- every slice
    id in the plan must carry a terminal `SliceCommitVerified` ledger record.
    """
    return frozenset(
        slice_id for slice_id, _status in _parse_slice_plan_rows(repo, feature_id)
    )


def _markdown_shipped_slices(repo: Path, feature_id: str) -> frozenset[str]:
    """The set of slice ids whose markdown `Status` cell is `shipped` (M12).

    The markdown fallback -- reached ONLY when the AT-completion ledger is
    fully absent (a pre-U3 feature). Fail-closed: any row whose `Status` cell
    is absent or outside the closed `{pending, shipped}` vocabulary raises
    `_SlicePlanParseUnresolved` -- never "assume shipped".
    """
    shipped: set[str] = set()
    for slice_id, raw_status in _parse_slice_plan_rows(repo, feature_id):
        status = (raw_status or "").strip().lower()
        if status not in _SLICE_PLAN_STATUS_VOCABULARY:
            raise _SlicePlanParseUnresolved(
                f"slice {slice_id} has an unrecognised Status cell "
                f"{raw_status!r}; expected one of "
                f"{sorted(_SLICE_PLAN_STATUS_VOCABULARY)}"
            )
        if status == "shipped":
            shipped.add(slice_id)
    return frozenset(shipped)


def _resolve_shipped_slice_set(
    repo: Path, feature_id: str
) -> tuple[frozenset[str], frozenset[str]]:
    """Resolve (planned_slices, shipped_slices) for the feature-end check.

    Primary path -- the U3 AT-completion ledger under the M7 fail-closed read
    contract: `verified_slices()` is "shipped". M12 fallback -- when the ledger
    file is fully ABSENT, parse the markdown `[REF] Slice Plan` `Status` column.
    A ledger present-but-corrupt raises `LedgerIntegrityViolation` (NOT a
    fallback) -- propagated to the caller's try/except.
    """
    from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger

    planned = _slice_plan_slice_ids(repo, feature_id)
    ledger = AtCompletionLedger(feature_id, repo)
    if ledger.ledger_path().is_file():
        # Ledger present -- `verified_slices()` reads under the M7 integrity
        # contract; a corrupt ledger raises LedgerIntegrityViolation here.
        return planned, ledger.verified_slices()
    # Ledger fully absent (pre-U3 feature) -- M12 markdown fallback only.
    return planned, _markdown_shipped_slices(repo, feature_id)


# The feature-end cycle records U4 asserts before a feature is closeable (F1).
# fix-oss-environmental-e2e-gate slice-02 (DESIGN / Where the Gate Lives RES-2):
# `EnvironmentalE2eGateRan` is the heartbeat the DELIVER feature-end
# orchestration step emits BEFORE `verify_environmental_e2e --mode run`
# returns. Its absence from the ledger means the env-e2e sub-step was skipped
# -- the U4 enforcer surfaces a missing-record block computed in the separate
# SubagentStop subprocess, independent of whether the gate itself ran.
# fix-walking-skeleton-feature-end-wiring slice-01: `WalkingSkeletonGateRan`
# is the heartbeat the walking-skeleton gate emits on entry. Its absence from
# the ledger means the walking-skeleton sub-step was skipped -- mirror of the
# env-e2e wiring, 5th sibling of the pre-7af95a3d2 shipped-but-unread class.
# fix-distill-signoff-feature-end-wiring slice-01: the two coverage-map
# touchpoint heartbeats (`CoverageMapVerifiedAtDistillExit` +
# `CoverageMapVerifiedAtDeliverExit`) emitted by the slice-06 gate are also
# required -- closes the named residue F-SLICE-06-U4-CONSUMER-MISSING from
# Gate D slice-06 commit `a8c9dc9d8` ("the gate emits the heartbeats but
# the consumer does not yet enforce them").
# f-nonbypassable-attestation slice-01 (DDD-4): `FullSuiteLegRan` is the
# feature-end full-suite leg's heartbeat. Its absence means the full suite never
# ran at feature-end -- the done-gate refuses on record-ABSENCE (6th sibling of
# the env-e2e / walking-skeleton / coverage-map heartbeat pattern). This frozenset
# is the absent-flavor FALLBACK; the live SSOT is `atdd_pure.yaml
# feature_end_required_records` (read by `_feature_end_required_records`), held
# EQUAL to it + to `verify_deliver_integrity.py:required` (AT-A6).
_REQUIRED_FEATURE_END_RECORDS = frozenset(
    {
        "CoverageMapVerifiedAtDeliverExit",
        "CoverageMapVerifiedAtDistillExit",
        "EBatchRefactorCompleted",
        "EnvironmentalE2eGateRan",
        "FeatureEndReviewVerdict",
        "FullSuiteLegRan",
        "WalkingSkeletonGateRan",
    }
)


# The lifecycle event + flavor keys the feature-end required-records profile is
# sourced from. The `subagent.stop` composition's `feature_end_required_records`
# field is the YAML home of the profile (gate-composition SSOT, DDD-1/DDD-3): the
# `_REQUIRED_FEATURE_END_RECORDS` frozenset above is the absent-flavor fallback,
# but the shipped `nWave/flavors/atdd_pure.yaml` carries the same six so the YAML
# is the single source (representation 3 -> 1).
_ATDD_PURE_FLAVOR_ID = "atdd_pure"
_SUBAGENT_STOP_EVENT_ID = "subagent.stop"
_FEATURE_END_REQUIRED_RECORDS_FIELD = "feature_end_required_records"

# The shipped flavor directory, resolved the same way `carpaccio_intercept.py`
# resolves it (`Path(__file__).resolve().parents[5]/nWave/flavors`). The
# `NWAVE_FLAVORS_DIR` env override points the gate-composition lookup at an
# alternate flavor directory (the SSOT override seam slice-04 wires).
_SHIPPED_FLAVORS_DIR = Path(__file__).resolve().parents[5] / "nWave" / "flavors"


def _feature_end_required_records() -> frozenset[str]:
    """The feature-end required-records profile the subagent.stop composition declares.

    Gate-composition SSOT (DDD-1/DDD-3): the profile is sourced from the flavor
    YAML's `subagent.stop` composition (`feature_end_required_records` field),
    NOT the hardcoded `_REQUIRED_FEATURE_END_RECORDS` frozenset. The
    `NWAVE_FLAVORS_DIR` env override selects the flavor directory; the shipped
    `nWave/flavors/` governs when it is unset. The frozenset is the absent-field
    fallback so a flavor without the field preserves today's six.
    """
    flavors_dir = Path(os.environ.get("NWAVE_FLAVORS_DIR") or str(_SHIPPED_FLAVORS_DIR))
    flavor_doc = subset_parser.load_file(flavors_dir / f"{_ATDD_PURE_FLAVOR_ID}.yaml")
    lifecycle_events = flavor_doc.get("lifecycle_events", {})
    composition = lifecycle_events.get(_SUBAGENT_STOP_EVENT_ID, [])
    for gate_spec in composition:
        if _FEATURE_END_REQUIRED_RECORDS_FIELD in gate_spec:
            return frozenset(gate_spec[_FEATURE_END_REQUIRED_RECORDS_FIELD])
    return _REQUIRED_FEATURE_END_RECORDS


def _missing_feature_end_cycle_records(repo: Path, feature_id: str) -> frozenset[str]:
    """The required feature-end cycle records absent from the U3 ledger (F1).

    slice-05 revision (Finding 1): "every slice shipped" is NOT sufficient for
    feature-end -- a feature with zero refactor + zero deep review would pass.
    The feature-end cycle must have written an `EBatchRefactorCompleted` record
    AND a `FeatureEndReviewVerdict` record (carrying the reviewer verdict_hash).
    Returns the set of required records still missing -- empty when the cycle
    is complete.

    fix-oss-environmental-e2e-gate slice-02: extended with
    `EnvironmentalE2eGateRan` -- a feature-end cycle that did not record the
    env-e2e gate heartbeat is mechanically blocked here as the env-e2e
    sub-step having been skipped.

    fix-walking-skeleton-feature-end-wiring slice-01: extended with
    `WalkingSkeletonGateRan` -- a feature-end cycle that did not record the
    walking-skeleton gate heartbeat is mechanically blocked here as the
    walking-skeleton sub-step having been skipped.

    fix-distill-signoff-feature-end-wiring slice-01: extended with the two
    coverage-map touchpoint heartbeats (`CoverageMapVerifiedAtDistillExit` +
    `CoverageMapVerifiedAtDeliverExit`) -- a feature-end cycle that did not
    record either touchpoint heartbeat is mechanically blocked here.
    Closes the named residue F-SLICE-06-U4-CONSUMER-MISSING from Gate D
    slice-06 commit `a8c9dc9d8`.

    Read under the M7 fail-closed integrity contract -- a corrupt ledger raises
    `LedgerIntegrityViolation`, propagated to the caller's try/except.
    """
    from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger

    ledger = AtCompletionLedger(feature_id, repo)
    recorded = ledger.feature_end_events()
    env_events = ledger.environmental_e2e_events()
    walking_skeleton = ledger.walking_skeleton_events()
    coverage_map = ledger.coverage_map_touchpoint_events()
    # f-nonbypassable-attestation slice-01 (DDD-4): the full-suite leg's
    # FullSuiteLegRan heartbeat (or its FullSuiteLegNotApplicable NA marker, which
    # reconciles the requirement for a target repo with no collectable contract
    # suite -- genericità, never a fake pass). Mirrors the CLI done-gate.
    full_suite = ledger.full_suite_leg_events()
    reconciled: set[str] = set()
    if "FullSuiteLegNotApplicable" in full_suite:
        reconciled.add("FullSuiteLegRan")
    return _feature_end_required_records() - (
        recorded
        | env_events
        | walking_skeleton
        | coverage_map
        | full_suite
        | reconciled
    )


def _handle_feature_end_gate(
    resolved: _AtddPureResolvedContext,
    hook_input: dict[str, object],
    hook_id: str,
) -> int:
    """Run the U4 feature-end terminal gate for a returning F_FINAL_REVIEW agent.

    Detection: the returning agent is in the `F_FINAL_REVIEW` phase AND all
    planned slices are shipped (derived from the U3 ledger under the M7
    fail-closed read contract -- M12 markdown fallback only on a fully-absent
    ledger; a corrupt ledger blocks with `LedgerIntegrityViolation`).

    On all-slices-shipped: run the feature-end integrity gate
    (`verify_deliver_integrity`) -- a non-zero exit blocks the feature as
    un-closeable. Until the last slice is shipped the F_FINAL_REVIEW return is
    not a feature-end return -- it falls through to the generic atdd_pure path.

    The whole branch body is wrapped in a try/except (M1): any exception is an
    `AtddPureHookInternalError` block + exit 0, never the bare exit-1 path.
    """
    from des.adapters.driven.logging.at_completion_ledger import (
        LedgerIntegrityViolation,
    )

    try:
        # M1 test seam: an injected fault exercises the fail-closed except path.
        if os.environ.get("NWAVE_U4_FORCE_HANDLER_FAULT") == "1":
            raise RuntimeError("injected feature-end intercept fault")

        cwd = hook_input.get("cwd", "")
        repo = Path(
            resolved.effective_cwd or (cwd if isinstance(cwd, str) else "") or "."
        )
        feature_id = resolved.project_id

        log_hook_invoked(
            "subagent_stop_feature_end_intercept",
            {
                "mode": "atdd_pure",
                "project_id": feature_id,
                "slice_id": resolved.slice_id,
                "atdd_pure_phase": resolved.atdd_pure_phase,
            },
            hook_id=hook_id,
        )

        planned, shipped = _resolve_shipped_slice_set(repo, feature_id)

        # Not all slices shipped yet -- this F_FINAL_REVIEW return is not a
        # feature-end return. Fall through to the generic atdd_pure handler.
        if not planned or not planned.issubset(shipped):
            return _handle_atdd_pure_return(resolved, hook_input, hook_id)

        # Feature-end cycle assertion (F1 -- slice-05 revision): every slice
        # being shipped is NOT sufficient. The feature-end cycle (E_BATCH_
        # REFACTOR + deep review) must have left its machine records in the
        # ledger. Absent either, the cycle never ran -- block fail-closed.
        missing_cycle = _missing_feature_end_cycle_records(repo, feature_id)
        if missing_cycle:
            return _emit_atdd_pure_block(
                f"feature-end cycle incomplete for {feature_id}: the "
                f"AT-completion ledger is missing the {sorted(missing_cycle)} "
                "record(s) -- the feature-end batch refactor and/or deep "
                "review never ran",
                "FeatureEndCycleIncomplete",
                feature_id=feature_id,
                missing=sorted(missing_cycle),
            )

        # Feature-end: every planned slice is shipped. Run the integrity gate.
        # `verify_deliver_integrity` resolves workflow.mode and the
        # AT-completion ledger from its `project_dir` argument -- the repo root
        # (the `.nwave/config.yaml` + `.nwave/telemetry/` live there).
        integrity_code = _run_gate_subprocess(
            "des.cli.verify_deliver_integrity",
            [str(repo)],
            repo,
            FEATURE_END_GATE_SUBPROCESS_TIMEOUT_SECONDS,
        )
        if integrity_code != 0:
            return _emit_atdd_pure_block(
                f"feature-end integrity gate rejected {feature_id}: "
                f"verify_deliver_integrity exited {integrity_code}",
                "FeatureEndGateRejected",
            )
        return 0

    except LedgerIntegrityViolation as exc:
        # M12: a corrupt ledger is a hard block, NEVER a silent degrade to the
        # markdown fallback or an undercount.
        return _emit_atdd_pure_block(
            f"the AT-completion ledger failed its integrity contract: {exc}",
            "LedgerIntegrityViolation",
            feature_id=resolved.project_id,
            detail=exc.detail,
        )
    except _SlicePlanParseUnresolved as exc:
        return _emit_atdd_pure_block(
            f"the markdown slice-plan Status column could not be parsed: {exc}",
            "SlicePlanParseUnresolved",
            feature_id=resolved.project_id,
        )
    except FileNotFoundError as exc:
        return _emit_atdd_pure_block(
            f"the feature-delta is missing for feature-end verification: {exc}",
            "FeatureEndGatePreconditionUnmet",
            missing="feature-delta-absent",
        )
    except subprocess.TimeoutExpired as exc:
        return _emit_atdd_pure_block(
            f"feature-end gate invocation timed out: {exc}",
            "GateInvocationTimeout",
            gate="verify_deliver_integrity",
        )
    except Exception as exc:
        # M1 fail-closed: an atdd_pure-branch exception is a block, never the
        # generic bare-exit-1 path (which carries no decision body).
        return _emit_atdd_pure_block(
            f"feature-end intercept handler error: {exc}",
            "AtddPureHookInternalError",
        )


# ---------------------------------------------------------------------------
# G-DISTILL-EXIT gate SubagentStop intercept
# (oss-hook-side-phase-injection slice-01 / D1 keystone)
# ---------------------------------------------------------------------------


def _witnessing_at_path(repo: Path, feature_file: Path) -> str | None:
    """Resolve the executable AT module a ``.feature`` carrier witnesses.

    The behavioral witness-check (slice-03) RUNS the AT module, not the
    ``.feature`` text. Convention (the DISTILL substrate): a carrier
    ``g-<name>.feature`` sits beside its executable ``test_g_<name>.py`` in the
    same directory. Returns the sibling ``test_*.py`` module path RELATIVE to
    the repo (the adapter copies + runs it from there), or ``None`` when no
    runnable AT module sibling exists.

    A carrier WITHOUT a runnable AT module sibling falls back to the slice-01
    syntactic verdict (witnessed-by-name): there is no AT to run the
    differential against, so the gate does NOT downgrade it. This preserves the
    slice-01/02 contract (a name-matched clause with only a carrier `.feature`
    stays silent) while slice-03's fixtures -- which DO plant runnable AT
    modules -- get the behavioral check.
    """
    stem = feature_file.stem  # e.g. "g-dt-genuine"
    if stem.startswith("g-"):
        candidate = feature_file.with_name(f"test_g_{stem[2:]}.py")
        if candidate.is_file():
            return str(candidate.relative_to(repo))
    siblings = sorted(feature_file.parent.glob("test_*.py"))
    if siblings:
        return str(siblings[0].relative_to(repo))
    return None


def _run_decision_table_traceability_gate(repo: Path, feature_id: str) -> None:
    """Warn-loud on decision-table clauses with no witnessing AT (slice-01).

    oss-upstream-gate-pair-traceability slice-01: the SYNTACTIC join. Reads the
    feature-delta decision-table + every ``.feature`` ``# clause:`` carrier under
    the repo, and emits a LOUD warning to the real process stderr naming each
    clause-ID that no acceptance test witnesses, adjacent to the
    ``unwitnessed-no-at`` token.

    NON-HALTING (DT-5 / the OSS hooks-only invariant): this gate only WARNS. It
    never blocks, never raises into the caller. The whole body is wrapped in a
    fail-open try/except so a traceability fault can never disturb the
    DISTILL->DELIVER move -- the existing verdict-completeness check downstream
    is the only halting authority on this boundary.

    The warning is written to ``sys.__stderr__`` (the interpreter's original
    stderr), NOT ``sys.stderr``: the SubagentStop handler runs under a
    ``contextlib.redirect_stderr`` whose buffer is discarded on the allow path,
    so a loud warning must address the real fd-2 to reach the operator.
    """
    try:
        delta_path = _feature_delta_path(repo, feature_id)
        if not delta_path.is_file():
            return
        clauses = DecisionTableParser().parse(delta_path.read_text(encoding="utf-8"))
        if not clauses:
            return
        feature_texts: list[str] = []
        runnable_feature_files: list[tuple[str, str]] = []
        for feature_file in repo.rglob("*.feature"):
            if not feature_file.is_file():
                continue
            text = feature_file.read_text(encoding="utf-8")
            feature_texts.append(text)
            at_path = _witnessing_at_path(repo, feature_file)
            if at_path is not None:
                runnable_feature_files.append((at_path, text))
        parser = ClauseIdFeatureParser()
        witnessed = parser.witnessed_clause_ids(feature_texts)
        # slice-03: upgrade the syntactic join to an EARNED behavioral verdict
        # via the isolated-copy differential witness-check (ADR-001). The port
        # is language-bound; the gate verdict logic stays pure. Non-halting.
        from des.adapters.driven.witness.perturbation_witness_adapter import (
            PerturbationWitnessAdapter,
        )

        clause_targets = parser.clause_targets(runnable_feature_files)
        witness_port = PerturbationWitnessAdapter(repo)
        result = DecisionTableTraceabilityGate().evaluate_with_witness(
            clauses, witnessed, clause_targets, witness_port
        )
        if result.verdict == "warn":
            print(result.warning, file=sys.__stderr__, flush=True)
        # slice-02 DT-10: record the traceability verdict in the AT-completion
        # ledger so the hand-off leaves a durable audit trail. A "warn" verdict
        # (>=1 unwitnessed clause) appends `DecisionTableTraceabilityWarned`; a
        # clean (all-witnessed) pass appends `DecisionTableTraceabilityVerified`.
        # The `…Verified` branch is symmetric but unwitnessed at slice-02 (no
        # slice-02 AT drives it) -- a minimal emit, not an over-built fixture.
        # Feature-scoped (slice_id="") via the legacy per-feature ledger
        # construction the DT-10 read-back resolves from.
        verdict_event = (
            "DecisionTableTraceabilityWarned"
            if result.verdict == "warn"
            else "DecisionTableTraceabilityVerified"
        )
        from des.adapters.driven.logging.at_completion_ledger import (
            AtCompletionLedger,
        )

        AtCompletionLedger(feature_id, repo).append_gate_event(
            event=verdict_event,
            slice_id="",
        )
    except Exception:
        # Fail-open: the traceability gate is non-halting; a fault here must
        # never block the DISTILL->DELIVER move (DT-5). A ledger-write failure
        # is swallowed here too, so DT-10's append can never halt the gate.
        pass


def _handle_distill_exit_gate(
    resolved: _AtddPureResolvedContext,
    hook_input: dict[str, object],
    hook_id: str,
) -> int:
    """Run the G-DISTILL-EXIT gate for a returning acceptance-designer (D_DISTILL).

    The gate refuses the DISTILL->DELIVER transition until every planned slice
    carries a signed `ATReviewVerdict`, and on success leaves a durable
    `WorkflowPhaseCompletedDistill` ledger record (the symmetric SUCCESS
    terminal, SF ADR-016).

    HARD INVARIANT (hook-can't-spawn-agent): the gate only BLOCKS / EMITS -- it
    never dispatches the reviewer (Claude Code hooks cannot spawn agents).

    Decision table (C5):
      denominator = `_slice_plan_slice_ids` (the SAME U4 resolves)
      numerator   = `ledger.review_verdict_slices()`
      - planned ⊆ verdict-signed  -> emit `WorkflowPhaseCompletedDistill` + allow
      - a planned slice unsigned   -> block `DistillExitVerdictIncomplete`
      - unparseable slice-plan     -> fail-closed block `SlicePlanParseUnresolved`
        (never a vacuous "zero planned slices" pass, mirror of U4)

    The whole branch body is wrapped in a try/except (M1): any exception is an
    `AtddPureHookInternalError` block + exit 0, never the bare exit-1 path.
    A block emits exit 0 (SubagentStop protocol -- exit 2 makes Claude Code
    ignore stdout).
    """
    from des.adapters.driven.logging.at_completion_ledger import (
        AtCompletionLedger,
        LedgerIntegrityViolation,
    )

    try:
        cwd = hook_input.get("cwd", "")
        repo = Path(
            resolved.effective_cwd or (cwd if isinstance(cwd, str) else "") or "."
        )
        feature_id = resolved.project_id

        log_hook_invoked(
            "subagent_stop_distill_exit_intercept",
            {
                "mode": "atdd_pure",
                "project_id": feature_id,
                "slice_id": resolved.slice_id,
                "atdd_pure_phase": resolved.atdd_pure_phase,
            },
            hook_id=hook_id,
        )

        # oss-upstream-gate-pair-traceability slice-01: run the decision-table
        # <-> AT traceability gate ONE CONCERN EARLIER than the
        # verdict-completeness check. It only WARNS-loud (non-halting, DT-5) --
        # it cannot block, so the existing verdict gate below is unchanged.
        _run_decision_table_traceability_gate(repo, feature_id)

        planned = _slice_plan_slice_ids(repo, feature_id)
        ledger = AtCompletionLedger(feature_id, repo)
        verdict_signed = ledger.review_verdict_slices()

        missing = planned - verdict_signed
        if missing:
            return _emit_atdd_pure_block(
                f"DISTILL exit refused for {feature_id}: the {sorted(missing)} "
                "planned slice(s) have no signed acceptance-test review verdict",
                "DistillExitVerdictIncomplete",
                feature_id=feature_id,
                missing=sorted(missing),
            )

        # Complete verdict set -- emit the symmetric success terminal and allow.
        ledger.append_workflow_phase_completed_distill()
        return 0

    except LedgerIntegrityViolation as exc:
        return _emit_atdd_pure_block(
            f"the AT-completion ledger failed its integrity contract: {exc}",
            "LedgerIntegrityViolation",
            feature_id=resolved.project_id,
            detail=exc.detail,
        )
    except _SlicePlanParseUnresolved as exc:
        return _emit_atdd_pure_block(
            f"the feature-delta slice plan could not be parsed: {exc}",
            "SlicePlanParseUnresolved",
            feature_id=resolved.project_id,
        )
    except FileNotFoundError as exc:
        return _emit_atdd_pure_block(
            f"the feature-delta is missing for DISTILL-exit verification: {exc}",
            "SlicePlanParseUnresolved",
            feature_id=resolved.project_id,
        )
    except Exception as exc:
        # M1 fail-closed: an atdd_pure-branch exception is a block, never the
        # generic bare-exit-1 path (which carries no decision body).
        return _emit_atdd_pure_block(
            f"DISTILL-exit gate handler error: {exc}",
            "AtddPureHookInternalError",
        )


def _handle_atdd_pure_return(
    resolved: _AtddPureResolvedContext,
    hook_input: dict,
    hook_id: str,
) -> int:
    """Dispatch an atdd_pure crafter return to the SubagentStop service (T-C).

    The atdd_pure return is execution-log-free: no execution-log path, no
    step id, no signal-file step lifecycle to resolve. The handler builds an
    atdd_pure-shaped SubagentStopContext (mode == "atdd_pure") and delegates;
    the service skips ExecutionLogReader entirely.

    Returns the hook exit code: 0 on allow, 0-with-JSON on block (exit 0 so
    Claude Code processes the block JSON).
    """
    from des.ports.driver_ports.subagent_stop_port import SubagentStopContext

    turns_used, tokens_used = _extract_execution_stats(hook_input)

    log_hook_invoked(
        "subagent_stop_resolved",
        {
            "agent_type": hook_input.get("agent_type"),
            "agent_id": hook_input.get("agent_id"),
            "mode": "atdd_pure",
            "project_id": resolved.project_id,
            "slice_id": resolved.slice_id,
            "atdd_pure_phase": resolved.atdd_pure_phase,
            "des_project_root_marker": resolved.project_root_marker,
        },
        hook_id=hook_id,
    )

    # Stale-agent timeout terminal (oss-spine-watchdog slice-03, #68 P2-E): a
    # pure ADD before the existing allow. When the returning agent's last
    # progress is older than the stale threshold AND no terminal exists for the
    # key, close it loud (StaleAgentClosed) -- a terminating INDETERMINATE: exit
    # 0, NO {decision:block} body. Every non-stale / has-terminal / error path
    # falls through fail-open to the existing service.validate return UNCHANGED.
    if _maybe_emit_stale_agent_closed(resolved):
        return 0

    service = service_factory.create_subagent_stop_service()
    decision = service.validate(
        SubagentStopContext(
            execution_log_path="",
            project_id=resolved.project_id,
            step_id="",
            cwd=resolved.effective_cwd or hook_input.get("cwd", ""),
            turns_used=turns_used,
            tokens_used=tokens_used,
            mode="atdd_pure",
            slice_id=resolved.slice_id,
            atdd_pure_phase=resolved.atdd_pure_phase,
        ),
        hook_id=hook_id,
    )

    transcript_path = hook_input.get("agent_transcript_path")
    if transcript_path:
        _maybe_track_skill_loads(transcript_path)

    if decision.action == "allow":
        return 0

    response = _build_block_notification(
        resolved.project_id, resolved.slice_id or "", "", decision
    )
    print(json.dumps(response))
    return 0


def _emit_wave_only_refire_terminal(
    declared_wave: str,
    project_id: str,
    reason: str,
    hook_id: str,
) -> int:
    """Break the wave-only re-fire loop with a terminating-LOUD INDETERMINATE.

    RC2/RC1 cure (docs/feedback/des-spine-ceremony-cost-attack-plan.md). The
    wave-only block keys on a DES-WAVE marker the agent CANNOT emit where the
    parser reads (RC1: it lives in the orchestrator's Task-prompt). So when a
    wave-only block re-fires (Claude Code re-invokes the Stop hook with
    ``stop_hook_active: true``), re-emitting ``{decision:block}`` makes no
    progress -- the agent loops unboundedly (RC2: the ~100k-per-dispatch
    wave-marker tax). Unlike atdd_pure (`_emit_bounded_block_terminal`) and the
    classic path (the `stop_hook_active` loop-break at
    subagent_stop_service.py:266), the wave-only path had NO loop-breaker.

    On a RE-FIRE this mirrors those two terminals: NO ``{decision:block}`` body
    on stdout, a LOUD ``sys.__stderr__`` warning that NAMES the loop (the real
    fd-2 that survives the handler's ``redirect_stderr`` -- same sink as
    `_emit_terminating_indeterminate`), exit 0. Claude Code then reaches a
    terminal Stop instead of re-firing. Enforcement is NOT bypassed: the wave
    floor stays armed and the review verdict stays unrecorded, so the downstream
    state-level cross-wave gate still refuses (fix-ask #2: wave-close derived
    from STATE, not from an unemittable marker).
    """
    log_hook_invoked(
        "subagent_stop_wave_only_refire_terminal",
        {
            "mode": "wave_only",
            "declared_wave": declared_wave,
            "project_id": project_id,
        },
        hook_id=hook_id,
    )
    print(
        "INDETERMINATE: wave-only re-fire terminal -- the wave-only block for "
        f"wave '{declared_wave}' (feature '{project_id}') re-fired "
        "(stop_hook_active), but the demanded DES-WAVE marker is unemittable by "
        f"the agent (RC1), so re-firing is futile (RC2: {reason}). Terminating "
        "this Stop loud instead of re-blocking. The original refusal STILL "
        "STANDS in STATE: the wave floor remains armed and the review verdict "
        "remains unrecorded, so the downstream cross-wave gate continues to "
        "enforce -- this terminal relocates enforcement to state, it does NOT "
        "bypass the gate.",
        file=sys.__stderr__,
        flush=True,
    )
    return 0


def _handle_wave_only_return(
    resolved: _WaveOnlyResolvedContext,
    hook_id: str,
    stop_hook_active: bool = False,
) -> int:
    """Dispatch a wave-only Agent()-dispatch return into validate (WGO-001).

    The wave-only return is execution-log-free (like atdd_pure): no
    execution-log path, no step id. The handler builds a wave-only-shaped
    SubagentStopContext (execution_log_path == "" AND step_id == "") and
    delegates; the service's wave-only guard runs the EXISTING wave
    review-verdict gate-out at Step -1 (it keys on the active floor wave +
    feature-delta, never on the execution log) and NEVER reads an execution log.

    Returns the hook exit code: 0 on allow, 0-with-{decision:block}-body on a
    refusal (exit 0 so Claude Code processes the block JSON -- exit 2 ignores
    stdout; subagent_stop_handler.py block protocol).
    """
    from des.ports.driver_ports.subagent_stop_port import SubagentStopContext

    log_hook_invoked(
        "subagent_stop_resolved",
        {
            "mode": "wave_only",
            "declared_wave": resolved.declared_wave,
            "project_id": resolved.project_id,
        },
        hook_id=hook_id,
    )

    service = service_factory.create_subagent_stop_service()
    decision = service.validate(
        SubagentStopContext(
            execution_log_path="",
            project_id=resolved.project_id,
            step_id="",
            cwd=resolved.effective_cwd,
            # fix-floor-auto-close-cross-wave: thread the returning agent identity
            # so the cross-wave auto-close fires on this LIVE path when the owner
            # terminally returns (WAVE_OWNERS[subagent_type] == active wave).
            subagent_type=resolved.subagent_type,
        ),
        hook_id=hook_id,
    )

    if decision.action == "allow":
        return 0

    # RC2/RC1: on a RE-FIRE break the loop loud instead of re-emitting the block
    # (mirrors `_emit_bounded_block_terminal` + the classic stop_hook_active
    # loop-break). The FIRST fire (stop_hook_active=False) keeps the gate-out
    # review veto's fail-closed block byte-stable below.
    if stop_hook_active:
        return _emit_wave_only_refire_terminal(
            resolved.declared_wave,
            resolved.project_id,
            decision.reason or "wave gate-out veto",
            hook_id,
        )

    print(json.dumps({"decision": "block", "reason": decision.reason}))
    return 0


def _handle_wave_only_unresolved(
    unresolved: _WaveOnlyUnresolved,
    hook_id: str,
    stop_hook_active: bool = False,
) -> int:
    """Refuse a DES-WAVE-bearing return the resolver could not resolve (DDD-6).

    The fail-closed boundary (WGO-001 slice-06): a return whose transcript
    carries a DES-WAVE marker -- so it IS a DES return -- that the wave-only
    resolver could not map to a governed wave context (out-of-vocabulary wave /
    missing DES-PROJECT-ID) degrades LOUD to a refusal, distinct from a genuine
    non-DES return (no DES-WAVE marker) which keeps the existing
    passthrough-allow. A DES-WAVE was clearly declared; the context is
    INDETERMINATE; INDETERMINATE degrades LOUD, never to a silent allow.

    Returns the hook exit code: 0-with-{decision:block}-body (exit 0 so Claude
    Code processes the block JSON -- exit 2 ignores stdout; the SubagentStop
    block protocol).
    """
    log_hook_invoked(
        "subagent_stop_wave_only_unresolved",
        {
            "mode": "wave_only",
            "declared_wave": unresolved.declared_wave,
            "project_id": unresolved.project_id,
            "reason": unresolved.reason,
        },
        hook_id=hook_id,
    )
    reason = (
        "WAVE_GATEOUT_INDETERMINATE: a wave-agent return declared a DES-WAVE "
        f"marker the wave boundary could not resolve -- {unresolved.reason}. An "
        "unresolvable DES return fails closed (degrade-LOUD), it is never "
        "silently allowed to close the wave."
    )
    # RC2/RC1: on a RE-FIRE break the loop loud instead of re-emitting the block
    # (mirrors `_emit_bounded_block_terminal` + the classic stop_hook_active
    # loop-break). The FIRST fire keeps the slice-06 fail-closed refusal below.
    if stop_hook_active:
        return _emit_wave_only_refire_terminal(
            unresolved.declared_wave,
            unresolved.project_id,
            unresolved.reason,
            hook_id,
        )

    print(json.dumps({"decision": "block", "reason": reason}))
    return 0


# ---------------------------------------------------------------------------
# Main handler
# ---------------------------------------------------------------------------


def handle_subagent_stop() -> int:
    """Handle subagent-stop command: validate step completion.

    Protocol translation only -- all decisions delegated to SubagentStopService.

    Claude Code sends: {"agent_id", "agent_type", "agent_transcript_path", "cwd", ...}
    DES context (project_id, step_id) is extracted from the agent's transcript.
    Non-DES agents (no markers in transcript) are allowed through.

    Returns:
        0 if gate passes or non-DES agent
        1 if error occurs (fail-closed)
        2 if gate fails (BLOCKS orchestrator)
    """
    hook_id = str(uuid.uuid4())
    start_ns = time.perf_counter_ns()
    exit_code = 0
    task_correlation_id: str | None = None
    turns_used: int | None = None
    tokens_used: int | None = None
    stderr_buffer = io.StringIO()
    try:
        with contextlib.redirect_stderr(stderr_buffer):
            stdin_result = read_and_parse_stdin("subagent_stop")

            if stdin_result.is_empty:
                return 0

            if stdin_result.parse_error:
                response = {"status": "error", "reason": stdin_result.parse_error}
                print(json.dumps(response))
                exit_code = 1
                return exit_code

            # The is_empty / parse_error guards above guarantee a parsed dict.
            hook_input = stdin_result.hook_input
            assert hook_input is not None  # narrowed by the guards above

            # Extract execution stats from hook_input
            turns_used, tokens_used = _extract_execution_stats(hook_input)

            # Diagnostic: confirm hook was invoked with agent details
            log_hook_invoked(
                "subagent_stop",
                {
                    "agent_type": hook_input.get("agent_type"),
                    "agent_id": hook_input.get("agent_id"),
                    "has_transcript": hook_input.get("agent_transcript_path")
                    is not None,
                },
                hook_id=hook_id,
            )

            # L1 token instrumentation — additive walk of the same transcript.
            # Fail-open per D4: never blocks the hook on instrumentation errors.
            _emit_token_usage_events(
                hook_input.get("agent_transcript_path"),
                agent_name=hook_input.get("agent_type"),
            )

            # Resolve DES context from either protocol
            des_context_result = _resolve_des_context(hook_input)

            # atdd_pure dispatch return (T-C): execution-log-free path.
            if isinstance(des_context_result, _AtddPureResolvedContext):
                # U2 (slice-02): a crafter returning from the per-slice commit
                # phase is intercepted by the exit-gate branch. After the 7→3
                # reduction the canonical word is "D_REFACTOR_COMMIT"; the legacy
                # "G_COMMIT" word still routes here (lossless replay). U4
                # (slice-04): a F_FINAL_REVIEW return is intercepted by the
                # feature-end branch (which itself falls through to the generic
                # handler until every planned slice is shipped). Other atdd_pure
                # phases fall through to the generic atdd_pure return handler.
                if des_context_result.atdd_pure_phase in _COMMIT_GATE_PHASES:
                    exit_code = _handle_g_commit_exit_gate(
                        des_context_result, hook_input, hook_id
                    )
                    return exit_code
                if des_context_result.atdd_pure_phase == _FEATURE_END_RETURN_PHASE:
                    exit_code = _handle_feature_end_gate(
                        des_context_result, hook_input, hook_id
                    )
                    return exit_code
                if des_context_result.atdd_pure_phase == "D_DISTILL":
                    exit_code = _handle_distill_exit_gate(
                        des_context_result, hook_input, hook_id
                    )
                    return exit_code
                exit_code = _handle_atdd_pure_return(
                    des_context_result, hook_input, hook_id
                )
                return exit_code

            # WGO-001 wave-only Agent()-dispatch return: execution-log-free path
            # reaching the EXISTING wave review-verdict gate-out at validate Step
            # -1 (sibling of the atdd_pure branch). A DES-WAVE return (no step-id)
            # MUST reach validate so the design/devops/discuss review veto fires.
            if isinstance(des_context_result, _WaveOnlyResolvedContext):
                # RC2/RC1: thread stop_hook_active so a wave-only RE-FIRE breaks
                # the loop (terminal) instead of re-emitting {decision:block}.
                exit_code = _handle_wave_only_return(
                    des_context_result,
                    hook_id,
                    stop_hook_active=bool(hook_input.get("stop_hook_active", False)),
                )
                return exit_code

            # WGO-001 fail-closed boundary (slice-06 / DDD-6): a DES-WAVE-bearing
            # return the resolver could NOT resolve (out-of-vocab wave / missing
            # project id) degrades LOUD to a refusal -- never the silent
            # passthrough-allow a genuine non-DES return keeps.
            if isinstance(des_context_result, _WaveOnlyUnresolved):
                # RC2/RC1: thread stop_hook_active so an unresolvable RE-FIRE
                # breaks the loop (terminal) instead of re-emitting the block.
                exit_code = _handle_wave_only_unresolved(
                    des_context_result,
                    hook_id,
                    stop_hook_active=bool(hook_input.get("stop_hook_active", False)),
                )
                return exit_code

            if des_context_result[0] is None:
                # Error or non-DES passthrough -- log it for diagnostics
                _, response, exit_code = des_context_result
                log_hook_invoked(
                    "subagent_stop_passthrough",
                    {
                        "reason": "non_des_or_error",
                        "agent_type": hook_input.get("agent_type"),
                        "agent_id": hook_input.get("agent_id"),
                        "has_transcript": hook_input.get("agent_transcript_path")
                        is not None,
                        "transcript_path": hook_input.get("agent_transcript_path"),
                        "exit_code": exit_code,
                    },
                    hook_id=hook_id,
                )
                return exit_code
            (
                execution_log_path,
                project_id,
                step_id,
                raw_marker,
                effective_cwd,
            ) = des_context_result

            # Audit enrichment (Rex pre-req #5): record the resolved
            # execution-log path and the DES-PROJECT-ROOT marker value so
            # post-hoc analysis can trace why a particular log was chosen.
            log_hook_invoked(
                "subagent_stop_resolved",
                {
                    "agent_type": hook_input.get("agent_type"),
                    "agent_id": hook_input.get("agent_id"),
                    "execution_log_path": execution_log_path,
                    "des_project_root_marker": raw_marker,
                    "project_id": project_id,
                    "step_id": step_id,
                },
                hook_id=hook_id,
            )

            # Read task_start_time and task_correlation_id from signal BEFORE removing it
            task_start_time = ""
            signal_data = des_task_signal.read_signal(
                project_id=project_id, step_id=step_id
            )
            if signal_data:
                task_start_time = signal_data.get("created_at", "")
                task_correlation_id = signal_data.get("task_correlation_id")

            # Clean up DES task signal (subagent finished)
            des_task_signal.remove_signal(project_id=project_id, step_id=step_id)

            # Delegate to application service
            from des.ports.driver_ports.subagent_stop_port import SubagentStopContext

            stop_hook_active = bool(hook_input.get("stop_hook_active", False))
            # Pass effective_cwd for commit verification: validated DES-PROJECT-
            # ROOT marker (worktree) when present, else hook_input cwd. This
            # ensures the commit-verifier inspects the repo where the crafter
            # actually committed, not the orchestrator's startup CWD.
            cwd = effective_cwd or hook_input.get("cwd", "")
            service = service_factory.create_subagent_stop_service()
            decision = service.validate(
                SubagentStopContext(
                    execution_log_path=execution_log_path,
                    project_id=project_id,
                    step_id=step_id,
                    stop_hook_active=stop_hook_active,
                    cwd=cwd,
                    task_start_time=task_start_time,
                    turns_used=turns_used,
                    tokens_used=tokens_used,
                ),
                hook_id=hook_id,
            )

            # Track skill loads from sub-agent transcript (fail-open)
            transcript_path = hook_input.get("agent_transcript_path")
            if transcript_path:
                _maybe_track_skill_loads(transcript_path)

            # Translate HookDecision to protocol response
            if decision.action == "allow":
                exit_code = 0
                return exit_code

            response = _build_block_notification(
                project_id, step_id, execution_log_path, decision
            )
            print(json.dumps(response))
            # Exit 0 so Claude Code processes the JSON (exit 2 ignores stdout)
            exit_code = 0
            return exit_code

    except Exception as e:
        # Fail-closed: any error blocks execution via stderr + exit 1
        stderr_capture = stderr_buffer.getvalue()[:STDERR_CAPTURE_MAX_CHARS]
        log_hook_error(
            "subagent_stop",
            e,
            stderr_capture,
        )
        print(f"SubagentStop hook error: {e!s}", file=sys.stderr)
        exit_code = 1
        return exit_code
    finally:
        duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
        decision_str = EXIT_CODE_TO_DECISION.get(exit_code, "error")
        log_hook_completed(
            hook_id=hook_id,
            handler="subagent_stop",
            exit_code=exit_code,
            decision=decision_str,
            duration_ms=duration_ms,
            task_correlation_id=task_correlation_id,
            turns_used=turns_used,
            tokens_used=tokens_used,
        )
