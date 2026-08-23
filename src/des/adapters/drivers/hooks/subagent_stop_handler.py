"""SubagentStop hook handler — terminal-by-construction subagent results.

Stable-design report 2026-08-19 §1.1 (`~/nwave-formal/2026-08-19-gates/
report/2026-08-19-stable-design.md`): the PreToolUse budget guard
(`pre_tool_use_handler._evaluate_subagent_budget_exhaustion`) RE-DERIVES a
subagent's turn count from its own transcript parse, then preemptively
denies further tool calls near an estimated threshold. That heuristic
re-derivation has TWO independently observed failure modes (Run 9: killed 4
calls past `maxTurns:40` with zero guard evidence; Run 10: 54 real calls
against a declared `maxTurns:45`, guard never fired) -- both because the
re-derivation can disagree with the platform's own ground truth. This
module is the producer-side fix: consume the platform's OWN SubagentStop
completion event -- fired once, authoritatively, when a subagent's turn
ends for ANY reason (Claude Code registers no handler for this event
today: `scripts/shared/hook_definitions.py` names it `_RETIRED_HOOK_ACTIONS`)
-- instead of re-deriving a fact the platform already owns.

Residual obligation, verified THIS pass (the one claim the stable-design
report flagged as unverified against the platform's own source): direct
inspection of the installed `claude` CLI binary's own hookInput-
construction code (`strings` extraction, SubagentStop branch) shows the
REAL payload shape is:

    {..., hook_event_name: "SubagentStop", stop_hook_active: <bool>,
     agent_id: <str>, agent_transcript_path: <str>, agent_type: <str, ""
     if unknown>, last_assistant_message: <str>, background_tasks: [...],
     session_crons: [...]}

There is NO `stop_reason`/termination-cause field anywhere in that
construction. `agda/StableDesign.agda`'s `PlatformStopReason`/
`isMaxTurnsStopDec` postulate (a decidable "was this a maxTurns stop"
predicate over an authoritative platform field) does NOT correspond to a
real field Claude Code sends -- the postulate is not dischargeable as
written. What DOES exist, and IS authoritative: `agent_type` (always a
key, unlike the PreToolUse envelope investigated in Run 9/10 -- confirmed
`?? ""` fallback, never absent), `agent_transcript_path` (the subagent's
OWN transcript, computed directly from `agent_id` -- no PreToolUse-style
parent-session derivation needed here), and `last_assistant_message` (the
platform's own record of what the subagent said on its final turn).

The construction this module actually delivers, honestly scoped to what
that evidence supports: SILENCE is still made unrepresentable (every
nw-* SubagentStop either finds the role's own terminal `<ROLE>-RESULT:`
line already present, or synthesizes one) -- but the synthesized
result carries a single generic `INDETERMINATE` cause ("SubagentStop
fired without the role's terminal line"), never a platform-sourced
`MaxTurnsExhausted`-specific label, because no such platform field exists
to source one from. `_subagent_transcript_turn_count`'s heuristic count
(if resolvable) is appended as a DESCRIPTIVE, explicitly-labelled hint in
the synthesized text, never as the trigger -- the trigger is always
"no terminal line found", determined once, authoritatively, HERE.

Delivery mechanism: `additionalContext` on this hook's own stdout is the
proven-working shape `subagent_start_handler.py` already uses for
SubagentStart -- but SubagentStop fires "right before a subagent...
concludes its response", so its own `additionalContext` would inject into
the CONCLUDING subagent's context, not root's; whether Claude Code
separately threads it back through the Agent tool's return value to root
is NOT verified in this pass. The mechanism this module can actually PROVE
works is a durable file (the same class of artefact
`des_task_signal.py`/`skill_tracking_hooks.py` already use), one per
`agent_id`, under `.nwave/des/subagent-results/` -- root's own recovery
path (documented in `nWave/skills/nw-auto/SKILL.md`) reads it when an
Agent-tool dispatch returns without a clear terminal line. `additionalContext`
is still emitted too, best-effort, in case the platform does thread it.

Wires the two previously-orphaned, correctly-shaped functions this
report's own inventory named "catalogued but not wired":
`des_task_signal.remove_signal` (its own docstring already says "Remove
signal when SubagentStop fires") and
`skill_tracking_hooks.maybe_track_skill_loads`.

Fail-open throughout: a hook that can crash a subagent's own termination
is worse than one that misses an edge case.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


_NWAVE_AGENT_PREFIX = "nw-"

#: Durable per-agent synthesized-result directory -- same `.nwave/des/`
#: root `des_task_signal.py`'s own signal files use.
_SUBAGENT_RESULT_DIR = Path(".nwave") / "des" / "subagent-results"


#: A NAMED in-process teammate's opaque id: ``a`` + the lane name + ``-`` +
#: a 16-hex suffix (e.g. ``aspeedfix-6c5c7f8505b9e7dd``,
#: ``arca-trailer-bad32bb962c324bc``). An UNNAMED Agent-tool dispatch is
#: ``a`` + 16 hex with NO dash, so it deliberately does not match.
_NAMED_AGENT_ID = re.compile(r"^a(?P<name>.+)-[0-9a-f]{16}$")


def _resolve_agent_type(agent_type: str, transcript_path: str | None) -> str:
    """The role this subagent actually played, not the label it was dispatched under.

    For an UNNAMED Agent-tool dispatch the platform's ``agent_type`` already
    IS the role (``nw-troubleshooter-reviewer``). For a NAMED in-process
    teammate it is the LANE NAME (``speedfix``): Claude Code 2.1.239's own
    in-process-teammate agent definition sets ``agentType: t.agentName`` and
    stashes the real role separately as ``customAgentType``; the SubagentStop
    hookInput's ``agent_type`` is sourced from the former. A bare
    ``startswith("nw-")`` gate therefore silently no-ops for every named
    nWave lane -- the exact silence this handler exists to make
    unrepresentable.

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


def _terminal_marker(agent_type: str) -> str:
    """The role's own terminal-result grammar line prefix -- the SAME
    convention `pre_tool_use_handler._subagent_budget_exhaustion_block`
    already emits in its HOW text (`f"{role.upper()}-RESULT"`), e.g.
    `NW-SOFTWARE-CRAFTER-RESULT`."""
    return f"{agent_type.upper()}-RESULT"


def _transcript_has_terminal_marker(transcript_path: str, marker: str) -> bool:
    """True iff `marker` appears in ANY assistant text block across the
    subagent's own transcript -- the fallback source when
    `last_assistant_message` is absent or empty. Fail-closed-to-False (never
    guesses present) on any read/parse problem: an unreadable transcript is
    exactly the case this handler exists to catch, not paper over."""
    try:
        with open(transcript_path, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return False
    for raw_line in reversed(lines):
        line = raw_line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("type") != "assistant":
            continue
        message = entry.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "text":
                continue
            text = block.get("text")
            if isinstance(text, str) and marker in text:
                return True
    return False


def _heuristic_turn_count_hint(transcript_path: str) -> str:
    """A DESCRIPTIVE, explicitly-labelled hint only -- never the trigger for
    this handler's own decision (see module docstring: no platform field
    exists to authoritatively distinguish maxTurns-exhaustion from any
    other silent stop). Reuses `_subagent_transcript_turn_count` -- the
    SAME counting logic the budget guard already calibrated against real
    killed transcripts -- rather than a second, independently-drifting
    count."""
    try:
        from des.adapters.drivers.hooks.pre_tool_use_handler import (
            _subagent_transcript_turn_count,
        )

        count = _subagent_transcript_turn_count(transcript_path)
    except Exception:
        count = None
    if count is None:
        return "own transcript's turn count could not be read"
    return f"own transcript shows {count} assistant turns (heuristic, not platform-authoritative)"


def _synthesize_terminal_result(
    agent_type: str, marker: str, transcript_path: str | None
) -> str:
    hint = (
        _heuristic_turn_count_hint(transcript_path)
        if transcript_path
        else "no transcript path available"
    )
    return (
        f"{marker}: verdict INDETERMINATE reason: SubagentStop fired for "
        f"{agent_type} without its own terminal {marker} line ({hint}). "
        "Synthesized by the SubagentStop handler -- the platform's own "
        "SubagentStop event carries no authoritative stop-cause field, so "
        "this cannot distinguish budget exhaustion from any other silent "
        "stop; treat as INDETERMINATE either way and re-dispatch or "
        "investigate."
    )


def _write_durable_result(agent_id: str, synthesized: str) -> None:
    """Best-effort durable write -- never raises past this function; a
    failure here must not prevent the rest of this fail-open handler from
    completing (cleanup, additionalContext emission)."""
    try:
        _SUBAGENT_RESULT_DIR.mkdir(parents=True, exist_ok=True)
        result_path = _SUBAGENT_RESULT_DIR / f"{agent_id}.txt"
        result_path.write_text(synthesized, encoding="utf-8")
        # The root dispatches a lane by NAME and never learns the opaque hex
        # suffix, so an id-keyed-only receipt is addressable by its writer
        # alone. Mirror it under the lane name the root actually holds
        # (`nw-auto`'s own recovery path). Unnamed ids carry no name and are
        # deliberately not aliased.
        named = _NAMED_AGENT_ID.match(agent_id)
        if named:
            alias = _SUBAGENT_RESULT_DIR / f"{named.group('name')}.txt"
            alias.write_text(synthesized, encoding="utf-8")
    except OSError:
        pass


def _run_cleanup(transcript_path: str | None) -> None:
    """Wires the two previously-orphaned, correctly-shaped SubagentStop
    consumers this report's own inventory named: `des_task_signal.
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
    """Handle subagent-stop hook: emit a synthesized terminal result when a
    nWave subagent's own turn ended without one.

    Reads JSON from stdin (Claude Code SubagentStop hook protocol). For
    non-nWave agents (`agent_type` absent, empty, or not `nw-`-prefixed):
    no-op, exit 0. For nWave agents: checks `last_assistant_message`
    (falling back to a transcript scan) for the role's own terminal
    `<ROLE>-RESULT:` line. If found: runs cleanup only. If NOT found:
    synthesizes an INDETERMINATE terminal result, writes it durably
    (`.nwave/des/subagent-results/<agent_id>.txt`), emits it as
    `additionalContext` best-effort, then runs cleanup.

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

        agent_id = hook_input.get("agent_id")
        transcript_path = hook_input.get("agent_transcript_path")
        transcript_path = transcript_path if isinstance(transcript_path, str) else None
        last_assistant_message = hook_input.get("last_assistant_message") or ""

        agent_type = _resolve_agent_type(agent_type, transcript_path)
        if not agent_type:
            return 0

        marker = _terminal_marker(agent_type)

        found = (
            isinstance(last_assistant_message, str) and marker in last_assistant_message
        )
        if not found and not last_assistant_message and transcript_path:
            found = _transcript_has_terminal_marker(transcript_path, marker)

        if found:
            _run_cleanup(transcript_path)
            return 0

        synthesized = _synthesize_terminal_result(agent_type, marker, transcript_path)
        if isinstance(agent_id, str) and agent_id:
            _write_durable_result(agent_id, synthesized)
        print(json.dumps({"additionalContext": synthesized}))
        _run_cleanup(transcript_path)
        return 0
    except Exception:
        return 0
