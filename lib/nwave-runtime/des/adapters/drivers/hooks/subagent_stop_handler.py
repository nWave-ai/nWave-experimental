"""SubagentStop hook handler — cleanup wiring, receipt synthesis retired.

Consumes the platform's OWN SubagentStop completion event -- fired once,
authoritatively, when a subagent's turn ends for ANY reason (Claude Code
registers no handler for this event on its own: `scripts/shared/
hook_definitions.py` names it `_RETIRED_HOOK_ACTIONS`). Its one remaining
job is to run the two previously-orphaned, correctly-shaped SubagentStop
consumers an earlier inventory pass named "catalogued but not wired":
`des_task_signal.remove_signal` (its own docstring: "Remove signal when
SubagentStop fires") and `skill_tracking_hooks.maybe_track_skill_loads`.

RETIRED HERE (see git history for the removal commit and its rationale):
a durable per-agent "terminal result" receipt this module used to
synthesize under `.nwave/des/subagent-results/<agent_id>.txt` whenever a
subagent's own final turn carried no recognized `<TOKEN>-RESULT` line.
Measured twice, independently, five days apart: every receipt population
ever produced (52/52 on 2026-08-22, then 11/11 on 2026-08-24 after an
unrelated grammar repair) was a synthesis, including for lanes that HAD
reported a real verdict -- a false "silence" signal, never a caught
defect. Its only plausible dependent, the K4 measurement harness, reads
raw session transcripts and git state directly and never referenced this
directory. Retired rather than repaired (GDP-10): the information the
receipt carried was always a strict derivative of the subagent's own
transcript, which any real consumer already has cheaper, direct access
to.

The `<agent_id>.txt`/`<lane-name>.txt` files this module wrote before the
removal are NOT deleted by it -- historical evidence, per-worktree, harm
no one sitting there unread.

Fail-open throughout: a hook that can crash a subagent's own termination
is worse than one that misses an edge case.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


_NWAVE_AGENT_PREFIX = "nw-"


def _resolve_agent_type(agent_type: str, transcript_path: str | None) -> str:
    """The role this subagent actually played, not the label it was dispatched under.

    For an UNNAMED Agent-tool dispatch the platform's ``agent_type`` already
    IS the role (``nw-troubleshooter-reviewer``). For a NAMED in-process
    teammate it is the LANE NAME (``speedfix``): Claude Code 2.1.239's own
    in-process-teammate agent definition sets ``agentType: t.agentName`` and
    stashes the real role separately as ``customAgentType`` in the teammate
    metadata; the SubagentStop hookInput's ``agent_type`` is sourced from the
    former. A bare ``startswith("nw-")`` gate therefore silently no-ops for
    every named nWave lane -- exactly the silence this resolution exists to
    close, so cleanup below still fires for a named lane's real nw-* role.

    The role is recovered from the sidecar the platform writes beside the
    transcript it hands us in ``agent_transcript_path``
    (``<transcript-stem>.meta.json``). Fail-open: an absent, unreadable,
    non-JSON or roleless sidecar yields ``""`` -- a no-op, never a guess.
    """
    if agent_type.startswith(_NWAVE_AGENT_PREFIX):
        return agent_type
    if not transcript_path:
        return ""
    try:
        sidecar = Path(transcript_path).with_suffix(".meta.json")
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    custom = meta.get("customAgentType") if isinstance(meta, dict) else None
    if isinstance(custom, str) and custom.startswith(_NWAVE_AGENT_PREFIX):
        return custom
    return ""


def _run_cleanup(transcript_path: str | None) -> None:
    """Wires the two previously-orphaned, correctly-shaped SubagentStop
    consumers an earlier inventory pass named: `des_task_signal.
    remove_signal` (its own docstring: "Remove signal when SubagentStop
    fires") and `skill_tracking_hooks.maybe_track_skill_loads`. Both are
    already fail-open internally; this wraps them again defensively so a
    future regression in either can never reach this handler's own
    fail-open contract."""
    try:
        from des.adapters.drivers.hooks import des_task_signal

        des_task_signal.remove_signal()
    except Exception:
        pass
    if transcript_path:
        try:
            from des.adapters.drivers.hooks.skill_tracking_hooks import (
                maybe_track_skill_loads,
            )

            maybe_track_skill_loads(transcript_path)
        except Exception:
            pass


def handle_subagent_stop() -> int:
    """Handle subagent-stop hook: run cleanup for a resolved nWave agent.

    Reads JSON from stdin (Claude Code SubagentStop hook protocol). For
    non-nWave agents (`agent_type` absent, empty, not `nw-`-prefixed even
    after named-teammate resolution): no-op, exit 0. For nWave agents: runs
    `_run_cleanup` (task-signal removal, skill-load tracking) and exits 0.

    Returns:
        0 always (fail-open: a hook firing during a subagent's own
        termination must never itself raise or block).
    """
    try:
        raw = sys.stdin.read()
        hook_input = json.loads(raw)
    except Exception:
        return 0

    try:
        agent_type = hook_input.get("agent_type") or ""
        if not isinstance(agent_type, str):
            return 0

        transcript_path = hook_input.get("agent_transcript_path")
        transcript_path = transcript_path if isinstance(transcript_path, str) else None

        agent_type = _resolve_agent_type(agent_type, transcript_path)
        if not agent_type:
            return 0

        _run_cleanup(transcript_path)
        return 0
    except Exception:
        return 0
