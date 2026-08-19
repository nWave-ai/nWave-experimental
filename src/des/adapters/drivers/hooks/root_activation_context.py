"""K3-A root activation — extends nw-mode-select availability to the root agent.

`subagent_start_handler.py`'s SubagentStart reminder addresses a spawned
sub-agent AFTER it starts; it never reaches the root/orchestrator itself,
which never receives a SubagentStart event. This module closes that gap by
reusing hooks already registered and already executed in the root's own
process:

- `PreToolUse`/`Agent` (`pre_tool_use_handler.handle_pre_tool_use`, the
  `pre-task` action) -- fires when root dispatches to a sub-agent;
- `PreToolUse`/`Write` and `PreToolUse`/`Edit`
  (`pre_write_handler.handle_pre_write`, the `pre-write`/`pre-edit` actions)
  -- fires when root modifies a file directly, without ever dispatching a
  sub-agent (the gap the Agent-only wiring left open).

No new hook is registered here -- this is a pure, testable predicate + message
builder wired into each handler's existing allow path (see
`pre_tool_use_handler.py`'s `decision.warning` sibling branch, and
`pre_write_handler.py`'s allow branch). Building the reminder text never
gates or persists anything on its own: a skipped reminder is not an error.
But the underlying observation this module exposes (`is_nwave_adjacent_write`)
also feeds `pre_write_handler.py`'s activation-routing-before-mutation gate,
which DOES block a pertinent Write/Edit when no `Skill(nw-mode-select)` call
has been observed -- so root context is not merely advisory end-to-end.
"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

from des.application.skill_tracking_service import RootModeState


# Run 9/10 correction: `agent_id`/`agent_type` are documented (Claude Code's
# own hooks reference) as fields specific to the SubagentStart/SubagentStop
# lifecycle events -- NEVER guaranteed on an ordinary PreToolUse/PreWrite
# envelope. Every identity-keyed decision in `pre_tool_use_handler.py` and
# `pre_write_handler.py` (the budget guard, host-scan lockdown, the
# crafter/architect/ATD/PO envelope gates, and `is_root_invocation` itself)
# either read `hook_input.get("agent_type")` directly or duplicated the same
# `not agent_id and not agent_type` expression inline -- each one a second,
# independent chance to silently misread a real subagent's own call as
# root's. THIS module is the ONE resolver both handlers already import from
# (`pre_tool_use_handler.py` imports `root_mode_handoff_block_reason` from
# here; `pre_write_handler.py` imports `build_root_write_mode_select_context`
# from here) -- the identity resolution belongs in the same one place, not
# reimplemented per call site.
_NWAVE_AGENT_PREFIX = "nw-"


def _agent_type_from_transcript_meta_sidecar(transcript_path: str) -> str | None:
    """Independent of whatever a live PreToolUse/PreWrite envelope carries
    turn-by-turn, every subagent transcript at
    `.../subagents/agent-<id>.jsonl` has a co-located `agent-<id>.meta.json`
    written ONCE at spawn time -- verified universal across every captured
    K4 run on this box (run 9's own nw-user-examiner, and independently a
    nw-software-crafter dispatch from an unrelated run): always
    `{"agentType": "nw-...", ...}`, always sitting next to its own
    `.jsonl`. GDP-8's witness corollary: a second, platform-authored axis of
    identity, consulted whenever the primary envelope field is not locally
    inspectable. Root is never mistakenly matched here: root's OWN
    transcript never sits inside a `subagents/` directory."""
    path = Path(transcript_path)
    if path.parent.name != "subagents" or not path.name.startswith("agent-"):
        return None
    meta_path = path.parent / f"{path.stem}.meta.json"
    try:
        meta_text = meta_path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        meta = json.loads(meta_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(meta, dict):
        return None
    sidecar_agent_type = meta.get("agentType")
    return sidecar_agent_type if isinstance(sidecar_agent_type, str) else None


def resolve_subagent_agent_type(hook_input: dict[str, object]) -> str | None:
    """The dispatched nw-* subagent's own declared role name -- resolved
    from the live envelope's `agent_type` field first (cheap, no I/O),
    falling back to the platform's own durable `subagents/agent-<id>.meta.
    json` sidecar (one extra read) only when that field is absent or not an
    `nw-` role. `None` for root/user (no resolvable identity from either
    source) and for a non-nWave agent."""
    agent_type = hook_input.get("agent_type")
    if isinstance(agent_type, str) and agent_type.startswith(_NWAVE_AGENT_PREFIX):
        return agent_type
    transcript_path = hook_input.get("transcript_path")
    if not isinstance(transcript_path, str) or not transcript_path:
        return None
    sidecar_agent_type = _agent_type_from_transcript_meta_sidecar(transcript_path)
    if isinstance(sidecar_agent_type, str) and sidecar_agent_type.startswith(
        _NWAVE_AGENT_PREFIX
    ):
        return sidecar_agent_type
    return None


def hook_input_has_agent_identity(hook_input: dict[str, object]) -> bool:
    """True iff this PreToolUse/PreWrite call did NOT originate from root --
    the canonical `not is_root_invocation` resolver. Resolved from the live
    envelope's `agent_id`/`agent_type` fields first (either truthy is
    sufficient: ANY identifiable caller, nWave role or not, is not root),
    falling back to the transcript meta-sidecar's OWN presence when both are
    absent -- a `subagents/agent-<id>.jsonl` transcript path with a
    co-located `.meta.json` proves a real dispatched agent owns this call,
    independent of whether that role happens to be an `nw-*` one, or of
    whether the sidecar's own `agentType` value parses. Root's own
    transcript never sits inside a `subagents/` directory, so this can
    never mistake root's own call for a subagent's."""
    if hook_input.get("agent_id") or hook_input.get("agent_type"):
        return True
    transcript_path = hook_input.get("transcript_path")
    if not isinstance(transcript_path, str) or not transcript_path:
        return False
    path = Path(transcript_path)
    if path.parent.name != "subagents" or not path.name.startswith("agent-"):
        return False
    meta_path = path.parent / f"{path.stem}.meta.json"
    return meta_path.is_file()


#: Markers that mean the dispatch already carries an explicit mode/wave
#: declaration -- re-surfacing the reminder would be friction, not orientation.
_MODE_ALREADY_DECLARED_MARKERS = ("DES-WAVE:", "DES-MODE:")

#: Phrases meaning the user already pinned a conversational posture (mirrors
#: nw-mode-select's own "Step 1 -- is a mode already explicit?").
_MODE_ALREADY_EXPLICIT_PHRASES = (
    "direct mode",
    "human-on-the-loop",
    "auto mode",
    "just do it",
)

ROOT_MODE_SELECT_REMINDER = (
    "nw-mode-select available: before continuing this nWave-adjacent work, "
    "invoke the nw-mode-select skill (Skill tool) to choose human "
    "(project each stage, wait for GO) or auto (ask once, then run) and to "
    "classify the work S/M/L -- unless the mode is already explicit in this "
    "conversation."
)


def root_mode_handoff_block_reason(state: RootModeState) -> str | None:
    """Explain the two invalid root states after mode selection."""
    if state is RootModeState.INVALID:
        return (
            "After nw-mode-select, emit exactly one valid "
            "'NW-MODE-SELECTED: <direct|human|auto> <S|M|L>' line before "
            "the next root tool action."
        )
    if state is RootModeState.AUTO_PENDING:
        return (
            "Auto M/L is selected but nw-auto is not engaged. Invoke "
            "Skill(nw-auto) as the next tool call; root must not inspect, "
            "dispatch, or mutate directly."
        )
    return None


def is_nwave_adjacent_dispatch(subagent_type: str | None) -> bool:
    """True iff this dispatch targets an nWave agent (`nw-*` subagent_type).

    A dispatch to a generic/non-nWave agent is out of scope: injecting the
    reminder there would be noise, not orientation.
    """
    return bool(subagent_type) and subagent_type.startswith("nw-")


def build_root_mode_select_context(
    prompt: str, subagent_type: str | None
) -> str | None:
    """Return the root orientation reminder, or None when it would be noise.

    Returns None when:
    - the dispatch is not nWave-adjacent (see `is_nwave_adjacent_dispatch`);
    - the prompt already carries an explicit mode/wave marker;
    - the prompt already states the mode in prose (direct/human/auto).
    """
    if not is_nwave_adjacent_dispatch(subagent_type):
        return None
    if any(marker in prompt for marker in _MODE_ALREADY_DECLARED_MARKERS):
        return None
    lowered = prompt.lower()
    if any(phrase in lowered for phrase in _MODE_ALREADY_EXPLICIT_PHRASES):
        return None
    return ROOT_MODE_SELECT_REMINDER


#: Any path segment naming one of these means the write is bookkeeping/
#: telemetry, never root's own code-modification act -- excluded regardless
#: of which top-level directory it lives under (covers both
#: `.nwave/telemetry/**` and `tests/.nwave/**`).
_NWAVE_ADJACENT_EXCLUDED_SEGMENTS = frozenset({".nwave"})


def is_nwave_adjacent_write(file_path: str | None) -> bool:
    """True iff a Write/Edit `file_path` is pertinent to root-activation.

    Pertinent means: any non-empty path, under any top-level directory (not
    restricted to a fixed set of recognised project roots -- an activated
    root cannot Write/Edit any user artifact regardless of its top-level
    directory name, including `hc/generated_plan.py`, docs, or an arbitrary
    top-level package) and not under any `.nwave/` tree (telemetry, session
    bookkeeping) -- a bookkeeping write is not "root starting to modify
    code".
    """
    if not file_path:
        return False
    parts = PurePosixPath(file_path.replace("\\", "/")).parts
    return not any(segment in _NWAVE_ADJACENT_EXCLUDED_SEGMENTS for segment in parts)


def build_root_write_mode_select_context(
    file_path: str | None, session_active: bool
) -> str | None:
    """Return the root orientation reminder for a Write/Edit, or None.

    Returns None when:
    - a deliver session is already active (mode/wave already engaged via DES
      markers elsewhere -- re-surfacing here would be noise, not orientation);
    - the file is not nWave-adjacent (see `is_nwave_adjacent_write`).

    Best-effort only: THIS reminder text never changes the block/allow
    decision. But a non-None return also marks the write as the one case
    where `pre_write_handler.py`'s activation-routing-before-mutation gate
    applies -- that gate DOES block the write when no `Skill(nw-mode-select)`
    call has been observed in the transcript, so the caller's overall
    allow/block outcome is not independent of this predicate.
    """
    if session_active:
        return None
    if not is_nwave_adjacent_write(file_path):
        return None
    return ROOT_MODE_SELECT_REMINDER
