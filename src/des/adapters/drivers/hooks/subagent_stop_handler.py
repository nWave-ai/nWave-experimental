"""SubagentStop handler — validates step completion after sub-agent returns.

Translates Claude Code's SubagentStop hook event (JSON stdin) into
SubagentStopService decisions (allow/block). Extracts DES context from
agent transcripts, manages signal file lifecycle, and emits audit events.

Extracted from claude_code_hook_adapter.py as part of P4 decomposition.
"""

import contextlib
import io
import json
import re
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from des.adapters.driven.filesystem.wave_active_filesystem_store import (
    WaveActiveFilesystemStore,
)
from des.adapters.driven.logging.audit_events import (
    AgentUsageObservedEvent,
    EventType,
)
from des.adapters.driven.time.system_time import SystemTimeProvider
from des.adapters.drivers.hooks import hook_protocol, service_factory
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
from des.domain.des_marker_parser import DesMarkerParser
from des.domain.repo_path_resolver import (
    feature_delta_path as _feature_delta_path,
)
from des.domain.wave_active import WAVE_VOCABULARY, WaveActiveRecord
from des.ports.driven_ports.audit_log_writer import AuditEvent
from des.ports.driver_ports.pre_tool_use_port import HookDecision


# ---------------------------------------------------------------------------
# Cross-wave-child exit symmetry (fix-po-charter-dispatch-marker-lane)
# ---------------------------------------------------------------------------


def _returning_inside_a_different_active_wave(repo: Path) -> bool:
    """True when the ACTIVE wave floor names a wave OTHER than ``distill``.

    RCA fix-po-charter-dispatch-marker-lane §4a/§7: the ONLY envelope that
    passes PreToolUse entry for a non-code-facing spine sub-dispatch (a PO
    charter, an examiner walk) issued INSIDE another wave's floor borrows the
    ``D_DISTILL`` + ``feature-end`` declaration. A genuine feature-wide
    DISTILL-wave completion returns while ``distill`` itself is the active
    wave (or no wave floor is armed -- the pre-wave-active-tracking
    baseline); a ``D_DISTILL``-phase return arriving while a DIFFERENT wave
    (e.g. ``deliver``) is active is, by construction, a cross-wave-child
    sub-dispatch that borrowed the declaration -- never a real feature-wide
    DISTILL exit. The active wave is reader-sourced (never self-reported);
    an absent/unreadable floor is NOT treated as cross-wave-child (fails
    toward the existing, already-verified gate behaviour).
    """
    state = WaveActiveFilesystemStore().read(repo)
    return isinstance(state, WaveActiveRecord) and state.wave != "distill"


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
_CAUSAL_ID_PATTERN = re.compile(r"<!--\s*DES-CAUSAL-ID\s*:\s*([^\s<]+)\s*-->")


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


def _extract_causal_id(text: str) -> str | None:
    """Return the exact opaque causal marker from one dispatch message."""
    match = _CAUSAL_ID_PATTERN.search(text)
    return match.group(1) if match is not None else None


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
        # WHAT: audit-log write failed (e.g. unreadable/unwritable audit
        # sink, serialization error).
        # WHY: this helper is documented "silently swallowing failures"
        # (see docstring) -- audit logging is observability, not
        # correctness-critical to the SubagentStop hook it's called from.
        # HOW: safe to continue -- the caller's hook flow proceeds
        # unaffected, only this audit record is lost.
        pass


def extract_des_context_from_transcript(transcript_path: str) -> dict[str, Any] | None:
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
        For an unresolved dispatch: dict with "project_id", "step_id",
        "project_root". For an atdd_pure dispatch: dict with "mode",
        "project_id", "slice_id", "atdd_pure_phase", "project_root",
        "at_kind" (the raw DES-AT-KIND marker value, or None when absent --
        fix-distill-exit-mechanical-seal-route slice-01) and "step_id" set
        to None. None when no DES markers are found.
    """
    if not Path(transcript_path).exists():
        _log_transcript_audit("HOOK_TRANSCRIPT_ABSENT", transcript_path)
        return None

    legacy_context: dict[str, Any] | None = None
    atdd_pure_context: dict[str, Any] | None = None

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
                            "at_kind": markers.at_kind,
                            "causal_id": _extract_causal_id(content),
                        }
                    continue

                # Classic dispatch: first complete marker set wins.
                if legacy_context is None and markers.project_id and markers.step_id:
                    legacy_context = {
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
    if legacy_context is not None:
        return legacy_context

    _log_transcript_audit("HOOK_TRANSCRIPT_NO_MARKERS", transcript_path)
    return None


# ---------------------------------------------------------------------------
# DES context resolution (direct protocol vs transcript-based)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _AtddPureResolvedContext:
    """Resolved DES context for an atdd_pure dispatch return (T-C).

    The handler converts this shape into a ``SubagentStopContext`` with
    ``return_kind=ATDD_PURE``. The slice is identified by ``slice_id``;
    ``effective_cwd`` is retained for audit emission and future (T-G) trailer
    verification.
    """

    project_id: str
    slice_id: str | None
    atdd_pure_phase: str | None
    project_root_marker: str | None
    effective_cwd: str
    # fix-distill-exit-mechanical-seal-route slice-01: the raw DES-AT-KIND
    # marker value echoed on the RETURNING agent's own transcript (mirrors the
    # grammar `carpaccio_intercept.py::_parse_at_kind_from_prompt` already
    # parses from the dispatch prompt). None when the marker is absent -- the
    # G-DISTILL-EXIT mechanical-seal route treats absence as compatible
    # (byte-identical to pre-fix behavior); an EXPLICIT non-"pytest-regression"
    # value blocks the route fail-closed (see `_mechanical_seal_cleared_slices`).
    at_kind: str | None = None
    causal_id: str | None = None


def _causal_envelope(resolved: _AtddPureResolvedContext) -> dict[str, str | None]:
    """Project intent correlation without claiming lifecycle evidence."""
    return {
        "correlation_status": (
            "correlated" if resolved.causal_id is not None else "unavailable"
        ),
        "correlation_id": resolved.causal_id,
        "lifecycle_status": "unavailable",
        "terminal_claim": None,
    }


def _emit_causal_envelope(resolved: _AtddPureResolvedContext) -> None:
    """Emit the same non-terminal causal projection for every atdd_pure exit."""
    print(json.dumps({"causal_envelope": _causal_envelope(resolved)}))


@dataclass(frozen=True)
class _WaveOnlyResolvedContext:
    """Resolved DES context for a wave-only Agent()-dispatch return (WGO-001).

    The shape an ``Agent()``-dispatched wave-agent (e.g. a DESIGN architect)
    return carries: a ``DES-WAVE`` marker + a ``DES-PROJECT-ID`` marker, with no
    atdd_pure markers. The handler converts this shape into a
    ``SubagentStopContext`` with ``return_kind=WAVE_ONLY``. It routes straight
    into ``SubagentStopService.validate`` so the EXISTING wave review-verdict gate-out
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


@dataclass(frozen=True)
class _TranscriptInaccessible:
    """A DECLARED ``agent_transcript_path`` that cannot be resolved to a
    readable file (fix-subagent-stop-silent-transcript).

    The fourth resolver outcome, mirroring ``_WaveOnlyUnresolved`` (DDD-6) for
    a sibling conflation: ``extract_des_context_from_transcript`` collapses
    "transcript inaccessible" (path absent, or present-but-unreadable) and
    "transcript accessible but marker-free" into the SAME ``None`` return
    (rca.md ROOT CAUSE A). A genuinely non-DES return (readable transcript,
    zero markers) still resolves this way and stays ``None`` -- keeps the
    existing byte-stable passthrough-allow (AT5). Only a DECLARED
    (non-empty) path that fails to resolve reaches this outcome (AT1-AT4);
    an ABSENT ``agent_transcript_path`` key never reaches here at all -- it
    is not a broken promise (RCA Q5, AT6).

    ``absence`` distinguishes "does not exist" (True) from "exists but could
    not be opened" (False) -- the charter's absence-vs-incapacity negative
    oracle (AT2): the diagnostic must never claim "no markers found" when the
    true condition is that the file could never be read at all.
    """

    transcript_path: str
    detail: str
    absence: bool


def _detect_transcript_inaccessible(
    transcript_path: str,
) -> _TranscriptInaccessible | None:
    """Probe ``transcript_path`` for the SAME accessibility primitive
    ``extract_des_context_from_transcript`` / ``_read_transcript_entries``
    already compute internally (``Path.exists()`` + open-and-catch
    ``OSError``/``PermissionError``) -- reused, not reinvented.

    Returns ``None`` when the path is accessible (the caller already knows
    it is marker-free, since this only runs when the extractor returned
    ``None``); otherwise a ``_TranscriptInaccessible`` naming WHAT failed.
    """
    path = Path(transcript_path)
    if not path.exists():
        return _TranscriptInaccessible(
            transcript_path=transcript_path, detail="does not exist", absence=True
        )
    try:
        with open(path):
            pass
    except (OSError, PermissionError) as exc:
        return _TranscriptInaccessible(
            transcript_path=transcript_path, detail=str(exc), absence=False
        )
    return None


def _resolve_des_context(
    hook_input: dict[str, Any],
) -> (
    _AtddPureResolvedContext
    | _WaveOnlyResolvedContext
    | _WaveOnlyUnresolved
    | _TranscriptInaccessible
    | tuple[None, dict[str, Any], int]
):
    """Resolve DES context from hook input.

    Supports the active Claude Code protocol: {"agent_transcript_path", "cwd", ...}.

    Returns:
        On error/passthrough: (None, response_dict, exit_code)
    """
    execution_log_path = hook_input.get("executionLogPath")
    project_id = hook_input.get("projectId")
    step_id = hook_input.get("stepId")

    uses_direct_des_protocol = execution_log_path or project_id or step_id

    if uses_direct_des_protocol:
        return None, _classic_mode_removed_payload(), 2

    # Claude Code protocol - extract DES context from transcript
    agent_transcript_path = hook_input.get("agent_transcript_path")
    cwd = hook_input.get("cwd", "")

    des_context = None
    if agent_transcript_path:
        des_context = extract_des_context_from_transcript(agent_transcript_path)
        if des_context is None:
            # fix-subagent-stop-silent-transcript: catch the DECLARED-but-
            # inaccessible case BEFORE the wave-only re-parse below can
            # swallow it into the same None (it inherits the identical
            # collapse one level deeper, rca.md Q2). Strictly inside this
            # `if agent_transcript_path:` truthy gate -- an ABSENT key never
            # reaches this branch at all (Q5, AT6).
            inaccessible = _detect_transcript_inaccessible(agent_transcript_path)
            if inaccessible is not None:
                return inaccessible

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

    # atdd_pure dispatch (T-C): marker-aware effective cwd is still computed
    # for audit / future trailer checks. The resolved shape is later converted
    # to the typed ``ATDD_PURE`` return kind.
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
            at_kind=des_context.get("at_kind"),
            causal_id=des_context.get("causal_id"),
        )

    return None, _classic_mode_removed_payload(), 2


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
        # FR-6: gate on a WELL-FORMED `<!-- DES-WAVE : x -->` marker, not the
        # bare substring. FR-5 stopped the fenced / user-role false-positive,
        # but an UNFENCED prose mention of the token "DES-WAVE" in the agent's
        # OWN (assistant) message -- e.g. an orchestrator narrating "the
        # DES-WAVE marker" in plain English -- still matched the raw-substring
        # gate, armed saw_des_wave_marker with no parseable declared_wave, and
        # degraded LOUD (WAVE_GATEOUT_INDETERMINATE) for the rest of the
        # session. Reuse the parser's marker detection (the same `_WAVE_PATTERN`
        # the extraction below already uses) so presence-check and
        # value-extraction share ONE notion of "is a DES-WAVE marker here":
        # a well-formed marker sets declared_wave (an out-of-vocab value still
        # matches `(\S+)` -> still arms -> still degrades LOUD), while a prose
        # mention leaves it None -> not a directive.
        markers = DesMarkerParser().parse(content)
        if markers.declared_wave is None:
            continue
        saw_des_wave_marker = True
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
    project_id: str,
    step_id: str,
    execution_log_path: str,
    decision: HookDecision,
) -> dict[str, Any]:
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


def _read_transcript_entries(transcript_path: str) -> list[dict[str, Any]]:
    """Parse a transcript JSONL file into a list of dict entries.

    Fail-open: malformed lines are skipped silently. Missing file yields
    empty list. Never raises.

    Both fail-open branches (absent file, unreadable file) emit a distinct
    audit event before returning ``[]`` -- an incapacity to read must never
    be indistinguishable from having read nothing (techdebt: transcript-read
    returns the same empty for missing/unreadable/marker-less files). This is
    an observability fix only: the return value/type is unchanged.
    """
    path = Path(transcript_path)
    if not path.exists():
        _log_transcript_audit("HOOK_TRANSCRIPT_ENTRIES_ABSENT", transcript_path)
        return []
    entries: list[dict[str, Any]] = []
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
    except (OSError, PermissionError) as e:
        _log_transcript_audit(
            "HOOK_TRANSCRIPT_ENTRIES_UNREADABLE", transcript_path, error=str(e)
        )
        return []
    return entries


# autonomous-consolidation-and-bugfix-loops slice-01 (D-1/D-8): the DISTILL-
# interim transcript-verdict-recovery parsing contract (Open Question 1, no
# DESIGN wave ran for this feature). A line matching this marker inside an
# ASSISTANT-role message is a stated verdict.
_VERDICT_MARKER_RE = re.compile(r"VERDICT:\s*(PASS|FAIL|BLOCKED)", re.IGNORECASE)


def _recover_verdict_from_transcript(
    transcript_path: str | None,
) -> tuple[str | None, str | None]:
    """Scan a stale-closed agent's OWN transcript for its last-stated verdict.

    DISTILL-interim parsing contract (feature-delta Open Question 1): a
    ``VERDICT:\\s*(PASS|FAIL|BLOCKED)`` marker (case-insensitive) inside an
    ASSISTANT-role message is a stated verdict -- never a user-role message
    (mirrors the existing role-scoping precedent in
    `_resolve_wave_only_context`, so a quoted/documented marker in
    user-injected content is never mistaken for the agent's own statement).
    Every assistant message is scanned (not only the last one -- a verdict
    "buried under noise" must still resolve); the LAST matching marker found,
    in transcript order, wins.

    Returns ``(verdict, None)`` when a marker was found, or ``(None, reason)``
    with a non-empty, honest ``reason`` when it was not -- absence of any
    matching marker, zero assistant messages, or unparseable assistant-turn
    content (silently dropped by `_read_transcript_entries`'s fail-open JSONL
    parse) all resolve here, NEVER a fabricated guess (D-8 negative-oracle
    mandate).
    """
    if not transcript_path:
        return None, "no transcript path was provided for this agent"
    saw_assistant_message = False
    recovered: str | None = None
    for entry in _read_transcript_entries(transcript_path):
        message = entry.get("message", {})
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        saw_assistant_message = True
        content = _normalize_message_content(message.get("content", ""))
        matches_in_message = list(_VERDICT_MARKER_RE.finditer(content))
        if matches_in_message:
            recovered = matches_in_message[-1].group(1).upper()
    if recovered is not None:
        return recovered, None
    if not saw_assistant_message:
        return (
            None,
            "the transcript carries no assistant-role messages to recover "
            "a verdict from",
        )
    return (
        None,
        "no assistant message in the transcript states a recognizable VERDICT marker",
    )


def _emit_token_usage_events(
    transcript_path: str | None,
    *,
    agent_name: str | None,
    feature_id: str | None = None,
    wave: str | None = None,
    slice_id: str | None = None,
    stage: str | None = None,
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
            slice_id=slice_id,
            stage=stage,
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


def _join_keys_from_resolved_context(
    des_context_result: (
        _AtddPureResolvedContext
        | _WaveOnlyResolvedContext
        | _WaveOnlyUnresolved
        | _TranscriptInaccessible
        | tuple[None, dict[str, Any], int]
    ),
) -> tuple[str | None, str | None, str | None]:
    """Derive (feature_id, slice_id, stage) join keys from a resolved DES context.

    DD-4: classification is by the resolved-context SHAPE, not by which
    downstream branch later consumes it -- every shape this resolver can
    return maps to its own join keys, or to (None, None, None) when no DES
    context could be established at all.

    * ``_AtddPureResolvedContext``  -> project_id, slice_id, atdd_pure_phase
    * ``_WaveOnlyResolvedContext``  -> project_id, None, declared_wave
    * unresolved, inaccessible, or error/passthrough shapes -> None, None, None
    """
    if isinstance(des_context_result, _AtddPureResolvedContext):
        return (
            des_context_result.project_id,
            des_context_result.slice_id,
            des_context_result.atdd_pure_phase,
        )
    if isinstance(des_context_result, _WaveOnlyResolvedContext):
        return (des_context_result.project_id, None, des_context_result.declared_wave)
    if isinstance(des_context_result, _WaveOnlyUnresolved):
        return (None, None, None)
    return (None, None, None)


def _extract_execution_stats(
    hook_input: dict[str, Any],
) -> tuple[int | None, int | None]:
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


def _classic_mode_removed_payload() -> dict[str, object]:
    """Closed public refusal for a direct legacy stop-context carrier.

    The diagnostic is READ from the resolver, never restated here: this hook and
    `des resolve-workflow-mode` refuse the same project for the same reason, so
    an operator must not get a different HOW depending on which one caught them.
    A second copy of the text drifts silently -- and a stale HOW is worse than a
    bare failure, because it sends the operator somewhere that no longer fixes
    anything.
    """
    from des.application.workflow_mode import refusal_diagnostic

    return {
        "outcome": "CLASSIC_MODE_REMOVED",
        "reason_code": "MIGRATION_REQUIRED",
        "effective_mode": None,
        "diagnostic": refusal_diagnostic("CLASSIC_MODE_REMOVED"),
    }


# ---------------------------------------------------------------------------
# atdd_pure return-path shared helpers
# ---------------------------------------------------------------------------


def _emit_atdd_pure_block(reason: str, event: str, **extra: object) -> int:
    """Print a `{decision:block}` body and return exit 0 (handler block protocol).

    SubagentStop blocks via `{"decision":"block"}` + exit 0 -- exit 2 makes
    Claude Code ignore stdout, and a bare exit 1 is an *error* (no decision
    body), which for an atdd_pure branch is fail-OPEN. Always exit 0 here.
    """
    payload: dict[str, object] = {"decision": "block", "reason": reason, "event": event}
    payload.update(extra)
    print(json.dumps(payload))
    return 0


# The bounded-block terminal bound (oss-spine-watchdog slice-02, RCA root #68):
# terminate ON the Nth identical block, so N-1 priors precede the terminating
# invocation. N=3 (DISCUSS D-4 / DESIGN OQ-3).
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
# The completed terminal `des commit-slice` writes (a member of the
# no-double-close recognized set, but NOT routed through the watchdog terminal
# helper -- it is the verified-commit success record). Read here, never written:
# no hook emits it any more.
_EVENT_SLICE_COMMIT_VERIFIED = "SliceCommitVerified"

# autonomous-consolidation-and-bugfix-loops slice-01 (D-1/D-8): the paired
# recovery record written alongside a `StaleAgentClosed` close, same tick,
# never orphaned. Exactly one of the two fires per close -- the success kind
# (a verdict was recovered) XOR the honest-failure kind (never a guess).
_EVENT_STALE_AGENT_VERDICT_RECOVERED = "StaleAgentVerdictRecovered"
_EVENT_STALE_AGENT_VERDICT_UNRECOVERABLE = "StaleAgentVerdictUnrecoverable"
# Marks a recovery record as derived from the agent's own transcript --
# distinguishable from an agent-reported completed terminal
# (`SliceCommitVerified` / `WorkflowPhaseCompletedGCommit`, charter Positive-2).
_SOURCE_TRANSCRIPT_RECOVERED = "transcript-recovered"


def _emit_terminating_indeterminate(
    project_id: str,
    effective_cwd: str,
    slice_id: str | None,
    event_name: str,
    reason_message: str,
    *,
    extra_fields: dict[str, object] | None = None,
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

    `extra_fields` (fix-bounded-block-names-how): optional additional keys
    threaded into the durable record verbatim (mirror the `pinned_commit_sha`
    / `block_reason` extra-field pattern `_emit_g_commit_ledger_event` already
    uses). Callers that pass nothing keep the byte-identical
    `{event, slice_id}` record shape -- this is additive, not a shape change
    for the existing StaleAgentClosed / CollectionCrashTerminal callers.
    """
    if slice_id:
        try:
            from des.adapters.driven.logging.at_completion_ledger import (
                AtCompletionLedger,
            )

            ledger = AtCompletionLedger(project_id, Path(effective_cwd or "."))
            record: dict[str, object] = {"event": event_name, "slice_id": slice_id}
            if extra_fields:
                record.update(extra_fields)
            ledger._append_record(record)
        except Exception:
            # Fail-open: the terminal decision already stands; ledger emission is
            # audit (mirror `_emit_g_commit_ledger_event`).
            pass
    # TODO(R-69-C): DV-2 WATCHDOG_* audit-log dual-emit. The audit-KPI sink is
    # not wired at the real-hook boundary yet; the durable ledger record above is
    # the KPI SSOT until R-69-C lands. Do NOT fabricate a sink here.
    print(reason_message, file=sys.__stderr__)


# fix-bounded-block-names-how: the HOW-to-recover `des <subcommand>` for each
# gate `block_reason` -- the concrete diagnostic that surfaces the REAL
# underlying gate failure the terminal stopped re-firing on. Names in the
# `des` single-entry-point registry (`src/des/cli/__main__.py`), not invented.
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


def _emit_verdict_recovery_record(
    project_id: str,
    effective_cwd: str,
    slice_id: str,
    transcript_path: str | None,
) -> None:
    """Pair a `StaleAgentClosed` close with a recovered-verdict record (D-1/D-8).

    autonomous-consolidation-and-bugfix-loops slice-01. Called immediately
    after `_emit_terminating_indeterminate` writes the `StaleAgentClosed`
    record, in the SAME hook invocation -- so a `StaleAgentClosed` record is
    never orphaned (D-8 no-orphan pairing). Scans the closed agent's OWN
    transcript (`_recover_verdict_from_transcript`, the DISTILL-interim
    parsing contract) and appends EXACTLY ONE recovery record:

      * `StaleAgentVerdictRecovered` (source="transcript-recovered",
        recovered_verdict=<PASS|FAIL|BLOCKED>) when a marker was found; or
      * `StaleAgentVerdictUnrecoverable` (source="transcript-recovered",
        reason=<honest non-empty reason>) when it was not -- never a
        fabricated guess (D-8 negative-oracle).

    Both record kinds carry `source="transcript-recovered"` so either is
    distinguishable from an agent-reported completed terminal
    (`SliceCommitVerified` / `WorkflowPhaseCompletedGCommit`, charter
    Positive-2) purely by field, independent of the recovery outcome.

    Fail-open (mirror `_emit_terminating_indeterminate`): a ledger-write
    failure here must not change the `StaleAgentClosed` terminal decision,
    which already stands by the time this is called.
    """
    verdict, reason = _recover_verdict_from_transcript(transcript_path)
    try:
        from des.adapters.driven.logging.at_completion_ledger import (
            AtCompletionLedger,
        )

        ledger = AtCompletionLedger(project_id, Path(effective_cwd or "."))
        if verdict is not None:
            ledger._append_record(
                {
                    "event": _EVENT_STALE_AGENT_VERDICT_RECOVERED,
                    "slice_id": slice_id,
                    "recovered_verdict": verdict,
                    "source": _SOURCE_TRANSCRIPT_RECOVERED,
                }
            )
        else:
            ledger._append_record(
                {
                    "event": _EVENT_STALE_AGENT_VERDICT_UNRECOVERABLE,
                    "slice_id": slice_id,
                    "reason": reason,
                    "source": _SOURCE_TRANSCRIPT_RECOVERED,
                }
            )
    except Exception:
        # Fail-open: the StaleAgentClosed terminal already stands; recovery
        # emission is audit (mirror `_emit_terminating_indeterminate`).
        pass


def _maybe_emit_stale_agent_closed(
    resolved: _AtddPureResolvedContext, transcript_path: str | None = None
) -> bool:
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

    autonomous-consolidation-and-bugfix-loops slice-01 (D-1/D-8): the SAME
    tick that emits `StaleAgentClosed` also pairs it with a recovered-verdict
    record derived from `transcript_path` (the closed agent's OWN transcript)
    via `_emit_verdict_recovery_record` -- so a `StaleAgentClosed` record is
    never orphaned. Pure ADD: the close decision above is unchanged.

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
        from des.domain.iso_utc import parse_iso_utc

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
        moment = parse_iso_utc(last_progress)
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
        # D-1/D-8: pair the close, same tick, with a recovered-verdict record
        # derived from the closed agent's own transcript -- never orphaned.
        _emit_verdict_recovery_record(
            resolved.project_id,
            resolved.effective_cwd,
            resolved.slice_id,
            transcript_path,
        )
        return True
    except Exception:
        # FAIL-SAFE: leave the agent alone on ANY error -- never close a possibly
        # working agent because of a ledger-read / parse failure.
        return False


# The closed status vocabulary of the markdown `[REF] Slice Plan` `Status`
# column (M12 fail-closed parse contract).
# G-DISTILL-EXIT mechanical-seal route (bug #94): the `[REF] Slice Plan`
# Annotation-cell token that names the regression-test file backing a
# pytest-regression bugfix slice, so `_mechanical_seal_cleared_slices` can
# discover which file to check without any table-parser change (the
# Annotation column is free text already). The regex itself now lives in
# `des.cli.carpaccio_format.REGRESSION_TEST_FILE_ANNOTATION_RE` -- the ONE
# shared locus (fix-des-next-blind-to-sealed-red, ZERO-DEFECTS dedup) --
# imported at point of use below rather than re-declared here.


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


def _mechanical_seal_cleared_slices(
    repo: Path, feature_id: str, missing: frozenset[str], at_kind: str | None = None
) -> frozenset[str]:
    """Slices in ``missing`` that clear G-DISTILL-EXIT via the mechanical-seal
    route (bug #94), mirroring the DELIVER-entry `check_at_review` mechanical-
    seal route (`carpaccio_slice_gate.py`) for a `pytest-regression` bugfix
    slice that carries valid mechanical evidence instead of a signed
    `ATReviewVerdict`.

    Only rows already in ``missing`` are considered (a verdict-signed slice
    needs no further evidence). A slice clears here when its `[REF] Slice
    Plan` Annotation cell carries a `@regression-test-file:<path>` token AND
    `carpaccio_slice_gate._mechanical_seal_satisfied` -- the EXACT predicate
    the DELIVER-entry gate already trusts (SSOT, reused not duplicated) --
    is ``True`` for that file: a fresh, content-bound `RedObserved` seal PLUS
    a satisfied negative-AT mandate.

    Fail-closed on every degraded input: no annotation token, an unparseable
    slice-plan (the caller already parsed it once via `_slice_plan_slice_ids`
    so this only re-degrades to an empty clear-set, never a crash), or a
    stale/absent seal all resolve to "not cleared" -- never a blanket bypass.

    D1 (deep-review finding, HIGH/blocking): ``at_kind`` gates the WHOLE route
    identically to the sibling DELIVER-entry check
    (`carpaccio_slice_gate.py:490`, ``if at_kind != "pytest-regression":
    ... return None`` -- the mechanical branch is unreachable for any other
    kind). Here, an EXPLICIT non-``"pytest-regression"`` value (a returning
    acceptance-designer positively declaring a Gherkin-kind dispatch via the
    echoed DES-AT-KIND marker) blocks the mechanical-seal route entirely --
    it never applies to a Gherkin-kind slice regardless of annotation/seal
    content. ``at_kind is None`` (the marker absent from the transcript --
    the pre-D1, byte-identical default for a dispatch that never carried this
    marker) proceeds with the existing per-slice annotation+seal check
    unchanged.
    """
    if not missing:
        return frozenset()
    if at_kind is not None and at_kind != "pytest-regression":
        return frozenset()
    from des.cli import carpaccio_format
    from des.cli.carpaccio_slice_gate import _mechanical_seal_satisfied

    try:
        text = _feature_delta_path(repo, feature_id).read_text(encoding="utf-8")
        rows = carpaccio_format.parse_slice_plan_rows(text)
    except (FileNotFoundError, carpaccio_format.GateError):
        return frozenset()

    cleared: set[str] = set()
    for row in rows:
        if row.slice_id not in missing:
            continue
        match = carpaccio_format.REGRESSION_TEST_FILE_ANNOTATION_RE.search(
            row.annotation
        )
        if match is None:
            continue
        regression_test_file = repo / match.group(1)
        if _mechanical_seal_satisfied(repo, regression_test_file):
            cleared.add(row.slice_id)
    return frozenset(cleared)


# fix-distill-exit-bugfix-lane-degrade: the DES-REGRESSION-TEST-FILE marker a
# returning D_DISTILL agent echoes on ITS OWN transcript, mirroring
# `carpaccio_intercept.py`'s identically-named marker (dispatch-prompt side)
# and `DesMarkerParser._AT_KIND_PATTERN`'s sibling (also return-transcript
# side). This marker is NOT yet threaded through `DesMarkerParser` /
# `_AtddPureResolvedContext` (grounding note verified by the acceptance-
# designer: no existing return-transcript path reads it) -- read directly
# here, scoped to the ONE consumer below, rather than widening the shared
# parser for a single call site.
_TRANSCRIPT_REGRESSION_TEST_FILE_PATTERN = re.compile(
    r"<!--\s*DES-REGRESSION-TEST-FILE\s*:\s*(\S+)\s*-->"
)


def _transcript_regression_test_file(agent_transcript_path: str | None) -> str | None:
    """The raw DES-REGRESSION-TEST-FILE marker value on the RETURNING agent's
    own transcript, or None when the marker is absent (or no transcript path
    is available). First match wins -- the bugfix-lane degrade below only
    ever needs a single, unambiguous file.
    """
    if not agent_transcript_path:
        return None
    for entry in _read_transcript_entries(agent_transcript_path):
        message = entry.get("message", {})
        if not isinstance(message, dict):
            continue
        content = _strip_fenced_regions(
            _normalize_message_content(message.get("content", ""))
        )
        match = _TRANSCRIPT_REGRESSION_TEST_FILE_PATTERN.search(content)
        if match is not None:
            return match.group(1)
    return None


def _bugfix_lane_mechanical_seal_clears(
    repo: Path, *, at_kind: str | None, agent_transcript_path: str | None
) -> bool:
    """True when a D_DISTILL return with NO feature-delta.md still clears
    G-DISTILL-EXIT via the mechanical-seal route (bug #94 alignment).

    A bugfix lane carries no `feature-delta.md` BY DESIGN (ADR-025 SLIM-
    crafter discipline) -- there is no `[REF] Slice Plan` Annotation cell to
    carry a `@regression-test-file:<path>` token for
    `_mechanical_seal_cleared_slices` to discover. The DES-REGRESSION-TEST-
    FILE marker on the RETURNING transcript is the only place left for that
    discovery to live for this lane.

    Fail-closed on every degraded input, mirroring
    `_mechanical_seal_cleared_slices`'s own discipline: an absent or explicit
    non-`"pytest-regression"` ``at_kind`` (no marker at all, or an explicit
    declaration of a different kind such as ``"gherkin"``), a missing
    DES-REGRESSION-TEST-FILE marker, or an unsatisfied seal (stale/absent
    `RedObserved` evidence, or an unsatisfied negative-AT mandate) all return
    False -- the caller then re-raises the original `FileNotFoundError` into
    the unchanged, fail-closed `SlicePlanParseUnresolved` block. This is
    never a blanket "no feature-delta.md -> pass": only an EXPLICIT
    mechanical-seal-eligible declaration backed by a genuinely satisfied seal
    clears.
    """
    if at_kind != "pytest-regression":
        return False
    regression_test_file = _transcript_regression_test_file(agent_transcript_path)
    if regression_test_file is None:
        return False
    from des.cli.carpaccio_slice_gate import _mechanical_seal_satisfied

    return _mechanical_seal_satisfied(repo, repo / regression_test_file)


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
        # gherkin-scope: the clause-carrier `# clause:` tag is structurally
        # bound to a Gherkin `.feature` file (the `g-<name>.feature` carrier
        # convention `_witnessing_at_path` documents) -- there is no pytest-
        # side equivalent of a "carrier" to discover here.
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
    carries EITHER a signed `ATReviewVerdict` OR valid mechanical-seal
    evidence (bug #94), and on success leaves a durable
    `WorkflowPhaseCompletedDistill` ledger record (the symmetric SUCCESS
    terminal, SF ADR-016).

    HARD INVARIANT (hook-can't-spawn-agent): the gate only BLOCKS / EMITS -- it
    never dispatches the reviewer (Claude Code hooks cannot spawn agents).

    Decision table (C5):
      denominator = `_slice_plan_slice_ids`
      numerator   = `ledger.approved_review_verdict_slices()` UNION
                    `_mechanical_seal_cleared_slices(missing, resolved.at_kind)`
                    (bug #94: the mechanical-seal route -- a fresh
                    `RedObserved` seal + satisfied negative-AT mandate for
                    the slice's declared `@regression-test-file`, reusing
                    `carpaccio_slice_gate._mechanical_seal_satisfied`, the
                    SAME predicate the DELIVER-entry gate already trusts).
                    D1: the route is gated on `resolved.at_kind` -- an
                    EXPLICIT non-`"pytest-regression"` DES-AT-KIND marker on
                    the returning transcript (e.g. `"gherkin"`) blocks the
                    WHOLE route fail-closed, mirroring the DELIVER-entry
                    sibling (`carpaccio_slice_gate.py:490`); an absent marker
                    proceeds unchanged (byte-identical pre-D1 behavior).
      - planned subset-of (verdict-signed UNION mechanical-seal-cleared) -> emit
        `WorkflowPhaseCompletedDistill` + allow
      - a planned slice neither signed nor mechanically sealed -> block
        `DistillExitVerdictIncomplete`
      - unparseable slice-plan     -> fail-closed block `SlicePlanParseUnresolved`
        (never a vacuous "zero planned slices" pass)
      - NO feature-delta.md at all (bugfix lane, ADR-025) AND the return is
        mechanical-seal-eligible for its OWN declared regression-test-file
        (`_bugfix_lane_mechanical_seal_clears`) -> emit
        `WorkflowPhaseCompletedDistill` + allow (fix-distill-exit-bugfix-
        lane-degrade: aligns this denominator read with
        `_mechanical_seal_cleared_slices`'s existing degrade on the SAME
        missing file); any other missing-file combination still falls
        through to the unchanged `SlicePlanParseUnresolved` block

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

        # Cross-wave-child exit symmetry (RCA fix-po-charter-dispatch-marker-
        # lane §4a/§7): a borrowed D_DISTILL declaration on a return arriving
        # while a DIFFERENT wave is active is never a genuine feature-wide
        # DISTILL completion -- verifying it against a slice plan the
        # feature-id legitimately never had traps the agent in a rejection
        # loop it cannot honestly escape. The honest declaration is exempt at
        # EXIT exactly as it is at ENTRY (symmetric fix).
        if _returning_inside_a_different_active_wave(repo):
            log_hook_invoked(
                "subagent_stop_distill_exit_intercept",
                {
                    "mode": "atdd_pure",
                    "project_id": feature_id,
                    "slice_id": resolved.slice_id,
                    "atdd_pure_phase": resolved.atdd_pure_phase,
                    "cross_wave_child_exempt": True,
                },
                hook_id=hook_id,
            )
            return 0

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

        try:
            planned = _slice_plan_slice_ids(repo, feature_id)
        except FileNotFoundError:
            # fix-distill-exit-bugfix-lane-degrade: a bugfix lane carries NO
            # feature-delta.md BY DESIGN (ADR-025 SLIM-crafter discipline) --
            # `_mechanical_seal_cleared_slices` a few lines below ALREADY
            # degrades gracefully on this SAME missing file, but this read
            # (the "planned" denominator) fires FIRST and, unchecked, would
            # crash into `SlicePlanParseUnresolved` before that branch is
            # ever reached. Align the two loci: when the returning agent is
            # mechanical-seal-eligible for its OWN declared regression-test-
            # file, the absence of a slice-plan is the EXPECTED shape for
            # this lane, not an error -- clear DISTILL-exit directly. Any
            # other combination (no at_kind, an explicit non-pytest-
            # regression at_kind, no marker, or an unsatisfied seal) is fail-
            # closed by `_bugfix_lane_mechanical_seal_clears` and re-raises
            # the original error into the unchanged block below.
            transcript_path = hook_input.get("agent_transcript_path")
            if _bugfix_lane_mechanical_seal_clears(
                repo,
                at_kind=resolved.at_kind,
                agent_transcript_path=(
                    transcript_path if isinstance(transcript_path, str) else None
                ),
            ):
                ledger = AtCompletionLedger(feature_id, repo)
                ledger.append_workflow_phase_completed_distill()
                return 0
            raise

        ledger = AtCompletionLedger(feature_id, repo)
        # APPROVED-only numerator (declared-facts-reachable-recorded slice-01
        # DD-1 follow-up, D04a): since commit 0303ecea5 a NEEDS_REVISION
        # verdict also appends an ATReviewVerdict record, so the any-verdict
        # `review_verdict_slices()` would silently count a REJECTED slice as
        # "signed". `approved_review_verdict_slices()` is the completeness
        # gate's own predicate; see its docstring for the full history.
        verdict_signed = ledger.approved_review_verdict_slices()

        missing = planned - verdict_signed
        if missing:
            missing = missing - _mechanical_seal_cleared_slices(
                repo, feature_id, missing, resolved.at_kind
            )

        # fix-distill-exit-jit-scope-probe: per-slice JIT authoring (atdd_pure
        # canonical, nw-distill Mandate 4) deliberately leaves later slices
        # absent from disk until their turn -- they can never carry a signed
        # verdict, so a still-missing slice with NO discoverable `.feature`/
        # pytest AT artifact anywhere (`feature_files_for_slice` empty) is
        # JIT-not-yet-reached, not a review omission. The feature's FIRST
        # planned slice is excluded from this carve-out: it is always the
        # slice this DISTILL return is FOR, so it must carry direct evidence
        # even when nothing was authored for it either (a genuinely empty
        # return is never "not yet reached"). A slice that IS present on disk
        # (even a scaffold-only `@skip` carrier) never qualifies -- a file's
        # mere presence is not a review, and it must stay in `missing`.
        excluded_slices: frozenset[str] = frozenset()
        if missing:
            from des.application.slice_at_completeness import (
                feature_files_for_slice,
            )

            plan_rows = _parse_slice_plan_rows(repo, feature_id)
            plan_order = [slice_id for slice_id, _status in plan_rows]
            plan_status = {
                slice_id: (status or "").strip().lower()
                for slice_id, status in plan_rows
            }
            first_planned_slice = plan_order[0] if plan_order else None
            # A slice is carved out of `missing` as JIT-not-yet-reached ONLY
            # when its plan `Status` is `pending` -- a `shipped` slice claims
            # delivery and so MUST carry a signed verdict (the
            # oss-hook-side-phase-injection keystone: a planned slice missing
            # its review keeps DISTILL open, regardless of disk presence).
            # Disk-absence alone is ambiguous -- it cannot tell a legitimately
            # deferred `pending` slice from a `shipped`-but-unreviewed omission
            # -- so the `pending` status is the discriminating signal; the
            # first planned slice and any slice with a discoverable artifact
            # still never qualify.
            excluded_slices = frozenset(
                slice_id
                for slice_id in missing
                if slice_id != first_planned_slice
                and plan_status.get(slice_id) == "pending"
                and not feature_files_for_slice(repo, slice_id, feature_id)
            )
            missing = missing - excluded_slices

        if missing:
            return _emit_atdd_pure_block(
                f"DISTILL exit refused for {feature_id}: the {sorted(missing)} "
                "planned slice(s) have no signed acceptance-test review "
                "verdict and no valid mechanical-seal evidence (fresh "
                "RedObserved seal + satisfied negative-AT mandate for a "
                "declared @regression-test-file)",
                "DistillExitVerdictIncomplete",
                feature_id=feature_id,
                missing=sorted(missing),
            )

        # Complete verdict set -- emit the symmetric success terminal and allow.
        ledger.append_workflow_phase_completed_distill(
            validated_slices=sorted(planned - excluded_slices),
            excluded_slices=sorted(excluded_slices),
        )
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
    hook_input: dict[str, Any],
    hook_id: str,
) -> int:
    """Dispatch an atdd_pure crafter return to the SubagentStop service (T-C).

    The handler builds a ``SubagentStopContext`` with
    ``return_kind=ATDD_PURE`` and delegates to the corresponding live service
    path.

    Returns the hook exit code: 0 on allow, 0-with-JSON on block (exit 0 so
    Claude Code processes the block JSON).
    """
    from des.ports.driver_ports.subagent_stop_port import (
        SubagentStopContext,
        SubagentStopReturnKind,
    )

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
    # autonomous-consolidation-and-bugfix-loops slice-01 (D-1): the closed
    # agent's own transcript path threads through so the SAME tick pairs the
    # close with a recovered-verdict record.
    if _maybe_emit_stale_agent_closed(
        resolved, hook_input.get("agent_transcript_path")
    ):
        return 0

    service = service_factory.create_subagent_stop_service()
    decision = service.validate(
        SubagentStopContext(
            project_id=resolved.project_id,
            return_kind=SubagentStopReturnKind.ATDD_PURE,
            cwd=resolved.effective_cwd or hook_input.get("cwd", ""),
            turns_used=turns_used,
            tokens_used=tokens_used,
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
    legacy path (the `stop_hook_active` loop-break at
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

    The handler builds a ``SubagentStopContext`` with
    ``return_kind=WAVE_ONLY`` and delegates; the service's wave-only path runs
    the EXISTING wave review-verdict gate-out at Step -1 (it keys on the active floor wave +
    feature-delta, never on the execution log) and NEVER reads an execution log.

    Returns the hook exit code: 0 on allow, 0-with-{decision:block}-body on a
    refusal (exit 0 so Claude Code processes the block JSON -- exit 2 ignores
    stdout; subagent_stop_handler.py block protocol).
    """
    from des.ports.driver_ports.subagent_stop_port import (
        SubagentStopContext,
        SubagentStopReturnKind,
    )

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
            project_id=resolved.project_id,
            return_kind=SubagentStopReturnKind.WAVE_ONLY,
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
    # (mirrors `_emit_bounded_block_terminal` + the legacy stop_hook_active
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
    # (mirrors `_emit_bounded_block_terminal` + the legacy stop_hook_active
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


def _transcript_inaccessible_reason(inaccessible: _TranscriptInaccessible) -> str:
    """WHAT/WHY/HOW diagnostic for a declared-but-inaccessible transcript.

    WHAT names the offending path verbatim and the failure kind (absence vs
    incapacity-to-read, AT2's negative oracle -- never a false "no markers
    found" claim). WHY states DES cannot verify whether the dispatch's exit
    gate ran (rca.md WHY 1B). HOW names a concrete corrective action -- never
    a bare "ask a human" deferral (AT3).
    """
    path = inaccessible.transcript_path
    if inaccessible.absence:
        what = f"the declared agent transcript {path!r} does not exist"
        how = (
            f"check the path with `ls -la {path}`; if the transcript was "
            "legitimately removed, re-run the dispatch so a fresh "
            "transcript is written"
        )
    else:
        what = (
            f"DES could not read the declared agent transcript {path!r} "
            f"({inaccessible.detail})"
        )
        how = f"check file permissions with `ls -l {path}` and restore read access"
    return (
        f"INDETERMINATE: {what}. DES cannot verify whether any exit gate "
        f"for this dispatch return was satisfied. HOW: {how}."
    )


def _handle_transcript_inaccessible(
    inaccessible: _TranscriptInaccessible,
    hook_id: str,
) -> int:
    """Degrade LOUD when a DECLARED ``agent_transcript_path`` is inaccessible
    (fix-subagent-stop-silent-transcript).

    Mirrors ``_handle_wave_only_unresolved`` (DDD-6): a declared-but-
    inaccessible transcript is a broken promise, distinguishable from BOTH
    the legitimate marker-free silent allow (a readable transcript with no
    DES markers, AT5) and the absent-key silent allow (no promise was ever
    made, AT6/RCA Q5). For a genuine atdd_pure return, an unreadable
    transcript means DES cannot verify whether the D_DISTILL exit gate was
    satisfied -- rca.md WHY 1B (a gate BYPASS, not merely missing operator
    feedback).

    Unlike the sibling ``_handle_wave_only_unresolved``, this NEVER emits a
    ``{"decision": "block"}`` body -- not even on the first fire (AT7). A
    broken transcript promise is an infrastructure fault the agent does not
    control and cannot resolve by being re-invoked; blocking would only
    invite Claude Code to re-fire against a condition retrying cannot cure.
    The outcome is purely informational instead: a distinct audit record (so
    it never files under the same ``subagent_stop_passthrough`` bucket a
    legitimate no-op gets, AT4) plus a LOUD ``sys.__stderr__`` diagnostic
    naming WHAT/WHY/HOW (AT1-AT3), at exit 0 -- which also means there is no
    re-fire loop to break in the first place (AT7 holds on both fires).
    """
    log_hook_invoked(
        "subagent_stop_transcript_inaccessible",
        {
            "transcript_path": inaccessible.transcript_path,
            "detail": inaccessible.detail,
            "absence": inaccessible.absence,
        },
        hook_id=hook_id,
    )
    print(
        _transcript_inaccessible_reason(inaccessible),
        file=sys.__stderr__,
        flush=True,
    )
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

            if hook_input.get("workflowMode") == "classic":
                print(json.dumps(_classic_mode_removed_payload()))
                exit_code = 2
                return exit_code

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

            # Resolve DES context from either protocol
            des_context_result = _resolve_des_context(hook_input)

            # L1 token instrumentation — additive walk of the same transcript.
            # Fail-open per D4: never blocks the hook on instrumentation errors.
            # DD-4: fires AFTER context resolution (not before, the root-cause
            # ordering bug) so feature_id/slice_id/stage can be threaded from
            # whichever resolved-context shape came back. Every branch below
            # returns AFTER this line, so every SubagentStop still emits
            # exactly one observation -- never dropped by the reorder.
            _usage_feature_id, _usage_slice_id, _usage_stage = (
                _join_keys_from_resolved_context(des_context_result)
            )
            _emit_token_usage_events(
                hook_input.get("agent_transcript_path"),
                agent_name=hook_input.get("agent_type"),
                feature_id=_usage_feature_id,
                slice_id=_usage_slice_id,
                stage=_usage_stage,
            )

            # atdd_pure dispatch return (T-C): execution-log-free path.
            if isinstance(des_context_result, _AtddPureResolvedContext):
                _emit_causal_envelope(des_context_result)
                # The U2 per-slice commit exit gate and the U4 feature-end gate
                # that used to intercept here are gone: a returning agent is no
                # longer blocked on E1/E2 completeness, a Gate-Scope trailer, a
                # SliceCommitVerified record or a feature-end record set. CI and
                # independent review remain the terminal evidence.
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

            # fix-subagent-stop-silent-transcript: a DECLARED
            # agent_transcript_path that could not be resolved to a readable
            # file (nonexistent, or existing but unreadable) is a broken
            # promise -- distinct from the legitimate marker-free silent
            # allow (AT5) AND the absent-key silent allow (AT6). Degrades
            # LOUD (never the silent passthrough-allow); never blocks (an
            # infrastructure fault the agent cannot fix by being re-invoked).
            if isinstance(des_context_result, _TranscriptInaccessible):
                exit_code = _handle_transcript_inaccessible(des_context_result, hook_id)
                return exit_code

            if des_context_result[0] is None:
                # Error or non-DES passthrough -- log it for diagnostics
                _, response, exit_code = des_context_result
                if response.get("outcome") == "CLASSIC_MODE_REMOVED":
                    print(json.dumps(response))
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
