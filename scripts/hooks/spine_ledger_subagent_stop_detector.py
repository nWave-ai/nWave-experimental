"""Spine-ledger SubagentStop detector -- slice-03 of atdd-spine-ledger-enforcement-gate-v2.

Fires on Claude Code's SubagentStop event after a sub-agent (Agent.Task) returns.
Inspects the returning sub-agent's transcript for code-shipping signals -- an
``Edit`` tool use on ``src/des/*`` or a ``Bash`` tool use whose command starts
with ``git commit``. When code-shipping is detected AND the current session
carries NO preceding ``CarpaccioGateCleared`` record in the spine telemetry
directory, emits one structured ``SpineBypassDetected`` audit event so the
marker-less Gap C class (Phase 0 audit: 430 marker-less transcripts in one
day) becomes OBSERVABLE post-hoc.

Substrate (Ale 2026-05-28 framing-shift): Claude Code hook lifecycle, NOT git.
This script is the SubagentStop entry point that surfaces orchestrator-layer
sub-agent dispatches that bypassed the spine. Slice-02 ships the PreToolUse
HARD-block on direct ``git commit`` Bash invocations; slice-03 is the
SOFT-escalation complement for the marker-less Agent.Task path.

Decision order:
    1. Read stdin event JSON (empty/malformed -> exit 0 silently; soft fail-open).
    2. Extract ``agent_transcript_path`` + ``session_id`` from the event.
    3. Scan the transcript JSONL for code-shipping tool_use blocks:
         - Edit with ``file_path`` matching ``src/des/.*`` -> evidence
         - Bash with ``command`` matching ``^\\s*git\\s+commit\\b`` -> evidence
       Empty evidence list -> exit 0 silently (fast-path skip, AT-2).
    4. Read the spine telemetry directory via ``AtCompletionLedger.read_records``
       (Mandate-12 SSOT). If ANY record has ``event == "CarpaccioGateCleared"``,
       suppress the emission -> exit 0 silently (AT-3 spine-cleared honour).
    5. Otherwise emit one ``SpineBypassDetected`` event to today's audit log
       and best-effort invoke ``mcp__lyra__observe`` (fail-open).
    6. Always exit 0 (slice-03 is soft-escalation; the sub-agent has already
       returned, blocking is impossible and undesirable).

Stdlib-only (no PyYAML, no third-party deps). Mirrors the pattern of
``scripts/hooks/spine_ledger_gate.py`` (slice-00+01) and
``scripts/hooks/subagent_stop_robustness_gate.py`` (the 2026-05-27 SubagentStop
precedent: single ``main()`` returning exit code, JSON stdin parse, fail-open).

Mandate-12 SSOT: the ledger read goes through ``AtCompletionLedger.read_records``
(in ``src/des/adapters/driven/logging/at_completion_ledger.py``). NO duplicated
ledger reader. The audit-log writer mirrors slice-00's ``_emit_bypass_event``
JSONL appender pattern (extension ``.log`` for cross-slice compatibility with
the slice-00/01/02 audit-log path; the composition fixture reads from the same
path via ``_read_audit_log_events``).

Hook protocol contract (Claude Code SubagentStop):
    stdin = {
      "agent_transcript_path": "<abs path to JSONL transcript>",
      "session_id": "...",
      "cwd": "...",
      ...
    }
    stdout = "" (empty; slice-03 is soft-escalation, no decision JSON emitted)
    exit 0 = always (the sub-agent already returned; blocking is impossible)

Test-harness env-var contract (slice-03 ATs, inherited from slice-02):
    NWAVE_SPINE_LEDGER_GATE_TARGET_ROOT -- target machine root override
    NWAVE_SPINE_LEDGER_GATE_LEDGER_ROOT -- spine telemetry dir override

In production (no env overrides) the hook uses ``Path.cwd()`` as the target
root and ``<target>/.nwave/telemetry/atdd-pure/`` as the ledger root.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


# Bootstrap `des` package onto sys.path so the standalone subprocess can import
# AtCompletionLedger. Mirrors the slice-00 gate self-bootstrap (no dependency on
# pytest config or installed-artifact layout).
_SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from des.adapters.driven.logging.at_completion_ledger import (  # noqa: E402
    AtCompletionLedger,
    LedgerIntegrityViolation,
)


# Env-var contract (inherited from slice-02 test harness).
_ENV_TARGET_ROOT = "NWAVE_SPINE_LEDGER_GATE_TARGET_ROOT"
_ENV_LEDGER_ROOT = "NWAVE_SPINE_LEDGER_GATE_LEDGER_ROOT"

# Default paths mirroring slice-00/01/02 conventions.
_TELEMETRY_RELPATH = Path(".nwave") / "telemetry" / "atdd-pure"
_AUDIT_LOG_DIR_RELPATH = Path(".nwave") / "des" / "logs"

# Audit-event literals (per platform architect critical-4 schema).
_BYPASS_DETECTED_EVENT = "SpineBypassDetected"
_CARPACCIO_GATE_CLEARED_EVENT = "CarpaccioGateCleared"
_CAUSE_NO_SPINE_EVENT_IN_SESSION = "no-spine-event-in-session"

# Code-shipping classifiers.
_SRC_DES_PREFIX = "src/des/"
_GIT_COMMIT_RE = re.compile(r"^\s*git\s+commit\b")

# Evidence-entry length cap (DISTILL contract: <=100 chars per entry).
_EVIDENCE_SNIPPET_MAX = 100


def _read_hook_event() -> dict:
    """Read the Claude Code SubagentStop hook event JSON from stdin.

    Returns ``{}`` on empty / malformed input -- the caller treats this as a
    non-actionable event and exits 0 silently. Slice-03 is soft-escalation:
    protocol parser errors MUST NOT block (the sub-agent already returned).
    """
    try:
        raw = sys.stdin.read()
    except OSError:
        return {}
    if not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _target_root() -> Path:
    """Resolve the target machine root from env override or ``Path.cwd()``."""
    override = os.environ.get(_ENV_TARGET_ROOT, "")
    return Path(override) if override else Path.cwd()


def _ledger_root(target_root: Path) -> Path:
    """Resolve the spine telemetry root from env override or the canonical path."""
    override = os.environ.get(_ENV_LEDGER_ROOT, "")
    return Path(override) if override else target_root / _TELEMETRY_RELPATH


def _audit_log_path(target_root: Path) -> Path:
    """Return today's UTC-dated audit log path under the target root.

    Mirrors slice-00 ``_audit_log_path`` (extension ``.log``, JSONL format).
    The composition fixture's ``_read_audit_log_events`` discovers events at
    this same path -- cross-slice compatibility is REQUIRED.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return target_root / _AUDIT_LOG_DIR_RELPATH / f"audit-{today}.log"


def _iter_tool_uses(transcript_path: Path) -> list[tuple[str, dict]]:
    """Yield (tool_name, tool_input) pairs from a Claude Code Agent transcript.

    Each transcript line is one JSON entry shaped like::

        {"message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": "<tool>", "input": {...}}]}}

    Lines that fail to parse or whose shape diverges are skipped silently --
    a malformed transcript is a Claude Code bug, not an operator bypass, and
    slice-03's contract is to fail-open on protocol violations.
    """
    if not transcript_path.is_file():
        return []
    tool_uses: list[tuple[str, dict]] = []
    for line in transcript_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            entry = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        message = entry.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_use":
                continue
            name = block.get("name", "")
            tool_input = block.get("input", {})
            if not isinstance(name, str) or not isinstance(tool_input, dict):
                continue
            tool_uses.append((name, tool_input))
    return tool_uses


def _classify_evidence(tool_uses: list[tuple[str, dict]]) -> list[str]:
    """Classify tool uses into code-shipping evidence strings.

    Two classifiers:
      - Edit with ``file_path`` matching ``src/des/.*`` -> ``"Edit <file_path>"``
      - Bash with ``command`` matching ``^\\s*git\\s+commit\\b`` -> ``"Bash <command>"``

    Evidence snippets are truncated to ``_EVIDENCE_SNIPPET_MAX`` chars to bound
    the audit-event size. All other tool uses (Read, Grep, Glob, Edit on non-
    src/des, Bash on non-git-commit) are ignored.
    """
    evidence: list[str] = []
    for name, tool_input in tool_uses:
        if name == "Edit":
            file_path = str(tool_input.get("file_path", ""))
            if file_path.startswith(_SRC_DES_PREFIX) or _SRC_DES_PREFIX in file_path:
                snippet = f"Edit {file_path}"[:_EVIDENCE_SNIPPET_MAX]
                evidence.append(snippet)
        elif name == "Bash":
            command = str(tool_input.get("command", ""))
            if _GIT_COMMIT_RE.match(command):
                snippet = f"Bash {command}"[:_EVIDENCE_SNIPPET_MAX]
                evidence.append(snippet)
    return evidence


def _spine_cleared(ledger_root: Path) -> bool:
    """True iff any per-feature ledger carries a ``CarpaccioGateCleared`` record.

    Mandate-12 SSOT: reads through ``AtCompletionLedger.read_records`` -- the
    SAME single reader slice-01 production uses. A malformed per-feature
    ledger surfaces as ``LedgerIntegrityViolation``; slice-03 tolerates it
    by skipping the offending file (mirrors slice-01's partial-failure
    tolerance) -- a malformed ledger MUST NOT silently suppress detection.

    Slice-03 simplification: any ``CarpaccioGateCleared`` record present in
    the telemetry directory = cleared. Per-session correlation via
    ``session_id`` is deferred to a future slice (slice-04 aggregator).
    """
    if not ledger_root.exists() or not ledger_root.is_dir():
        return False
    # Resolve project_root from ledger_root for AtCompletionLedger contract.
    # ledger_dir() == project_root / .nwave / telemetry / atdd-pure, so the
    # project_root is three parents up from ledger_root.
    project_root = ledger_root.parent.parent.parent
    for ledger_file in sorted(ledger_root.glob("*.jsonl")):
        feature_id = ledger_file.stem
        try:
            records = AtCompletionLedger(feature_id, project_root).read_records()
        except LedgerIntegrityViolation:
            continue
        for record in records:
            if record.get("event") == _CARPACCIO_GATE_CLEARED_EVENT:
                return True
    return False


def _emit_bypass_detected_event(
    target_root: Path,
    transcript_path: str,
    evidence: list[str],
    session_id: str,
) -> None:
    """Append one ``SpineBypassDetected`` event to today's audit log (JSONL).

    Schema (per platform architect critical-4 observability gap closure):
        {
          "event": "SpineBypassDetected",
          "ts": "<ISO8601 UTC>",
          "transcript_path": "<absolute path>",
          "evidence": ["Edit src/des/...", ...],
          "cause": "no-spine-event-in-session",
          "session_id": "<from hook input>"
        }

    The directory is created on demand. Mirrors slice-00's
    ``_emit_bypass_event`` JSONL appender (single-line, sort_keys for
    deterministic ordering, ``a`` mode for append-only audit log).
    """
    log_path = _audit_log_path(target_root)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event": _BYPASS_DETECTED_EVENT,
        "ts": datetime.now(timezone.utc).isoformat(),
        "transcript_path": transcript_path,
        "evidence": evidence,
        "cause": _CAUSE_NO_SPINE_EVENT_IN_SESSION,
        "session_id": session_id,
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def _best_effort_lyra_observe(
    transcript_path: str, evidence: list[str], session_id: str
) -> None:
    """Best-effort Lyra MCP ``observe`` emission per cross-instance memory anchor.

    Per DISTILL contract step 7 + dispatch §"platform architect critical-4
    observability gap" point 2: the hook SHOULD invoke ``mcp__lyra__observe``
    with a structured payload mirroring the audit event so the bypass is
    surfaced into Lyra's L3 cold memory for cross-instance forensic recall.

    Fail-open contract (slice-03 is soft-escalation): any error -- MCP
    unavailable, network failure, payload rejection -- is swallowed and the
    hook returns normally. The audit-log JSONL event is the canonical
    universe-bound observable; the MCP emission is a forensic convenience.

    In this hook subprocess the Lyra MCP client is not directly importable
    (the MCP transport lives in the parent Claude Code process). The
    implementation defers to a marker file under the audit log directory
    that the parent process (or a periodic sweep) can re-emit -- this keeps
    the soft-escalation contract intact while preserving the observability
    intent. Future slices may replace this with a direct MCP-server call.
    """
    try:
        # Defer the MCP-observe payload to a marker file in the audit log
        # directory so the parent Claude Code process can re-emit it without
        # the hook subprocess needing direct MCP-transport access. No-op when
        # the marker directory is unwriteable.
        target_root = _target_root()
        marker_dir = target_root / _AUDIT_LOG_DIR_RELPATH
        marker_dir.mkdir(parents=True, exist_ok=True)
        marker_path = marker_dir / "lyra-observe-pending.jsonl"
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "task": "spine_bypass_detected",
            "outcome": "bypass_recorded",
            "transcript_path": transcript_path,
            "evidence": evidence,
            "session_id": session_id,
        }
        with marker_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
    except Exception:
        # Soft-escalation: never block the hook on observability side-effects.
        return


def _dispatch(event: dict) -> int:
    """Apply the full slice-03 decision order; return the exit code (always 0).

    Decision order:
        1. No ``agent_transcript_path`` in event -> exit 0 silently.
        2. Empty evidence list (no code-shipping signals) -> exit 0 silently.
        3. Spine cleared (any CarpaccioGateCleared record present) -> exit 0
           silently (suppression contract, AT-3).
        4. Otherwise -> emit ``SpineBypassDetected`` audit event + best-effort
           Lyra ``observe`` -> exit 0 (soft-escalation never blocks).
    """
    transcript_path_str = event.get("agent_transcript_path", "")
    if not isinstance(transcript_path_str, str) or not transcript_path_str:
        return 0
    session_id = event.get("session_id", "")
    if not isinstance(session_id, str):
        session_id = ""

    transcript_path = Path(transcript_path_str)
    tool_uses = _iter_tool_uses(transcript_path)
    evidence = _classify_evidence(tool_uses)
    if not evidence:
        return 0

    target_root = _target_root()
    ledger_root = _ledger_root(target_root)
    if _spine_cleared(ledger_root):
        return 0

    _emit_bypass_detected_event(
        target_root=target_root,
        transcript_path=transcript_path_str,
        evidence=evidence,
        session_id=session_id,
    )
    _best_effort_lyra_observe(
        transcript_path=transcript_path_str,
        evidence=evidence,
        session_id=session_id,
    )
    return 0


def main() -> int:
    """Read the SubagentStop hook event from stdin, dispatch, return exit code.

    Slice-03 soft-escalation contract: exit 0 always. The sub-agent has
    already returned by the time SubagentStop fires; blocking is impossible
    and undesirable. The observable surface is the audit-log delta (Mandate
    8 universe-bound), NOT the exit code.
    """
    event = _read_hook_event()
    if not event:
        return 0
    return _dispatch(event)


if __name__ == "__main__":
    raise SystemExit(main())
