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
builder wired into each handler's existing non-blocking allow path (see
`pre_tool_use_handler.py`'s `decision.warning` sibling branch, and
`pre_write_handler.py`'s allow branch). It never sequences, gates, or persists
anything: a skipped reminder is not an error, and a printed one never changes
the allow/block decision.
"""

from __future__ import annotations

from pathlib import PurePosixPath


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
    "consider ~/.claude/skills/nw-mode-select/SKILL.md to choose human "
    "(project each stage, wait for GO) or auto (ask once, then run) and to "
    "classify the work S/M/L -- unless the mode is already explicit in this "
    "conversation."
)


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


#: Top-level directories a Write/Edit is considered "nWave-adjacent" under.
#: Deliberately narrow (not `docs/`): a purely historical doc edit must not
#: produce noise, and this predicate has no prose to read (Write/Edit carries
#: no `prompt`), so it stays conservative rather than guessing intent.
_NWAVE_ADJACENT_ROOTS = frozenset({"src", "nWave", "tests", "scripts"})

#: Any path segment naming one of these means the write is bookkeeping/
#: telemetry, never root's own code-modification act -- excluded regardless
#: of which top-level root it lives under (covers both `.nwave/telemetry/**`
#: and `tests/.nwave/**`).
_NWAVE_ADJACENT_EXCLUDED_SEGMENTS = frozenset({".nwave"})


def is_nwave_adjacent_write(file_path: str | None) -> bool:
    """True iff a Write/Edit `file_path` is pertinent to root-activation.

    Pertinent means: under one of the recognised project roots (`src/`,
    `nWave/`, `tests/`, `scripts/`) and not under any `.nwave/` tree
    (telemetry, session bookkeeping) -- a bookkeeping write is not "root
    starting to modify code".
    """
    if not file_path:
        return False
    parts = PurePosixPath(file_path.replace("\\", "/")).parts
    if any(segment in _NWAVE_ADJACENT_EXCLUDED_SEGMENTS for segment in parts):
        return False
    return any(segment in _NWAVE_ADJACENT_ROOTS for segment in parts)


def build_root_write_mode_select_context(
    file_path: str | None, session_active: bool
) -> str | None:
    """Return the root orientation reminder for a Write/Edit, or None.

    Returns None when:
    - a deliver session is already active (mode/wave already engaged via DES
      markers elsewhere -- re-surfacing here would be noise, not orientation);
    - the file is not nWave-adjacent (see `is_nwave_adjacent_write`).

    Best-effort only: the caller wires this into its allow path and must
    never let it influence the block/allow decision itself.
    """
    if session_active:
        return None
    if not is_nwave_adjacent_write(file_path):
        return None
    return ROOT_MODE_SELECT_REMINDER
