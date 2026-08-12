"""K3-A root activation on Write/Edit: covers root's own direct file edits.

`build_root_mode_select_context` (PreToolUse/Agent) only fires when root
dispatches a sub-agent -- it never fires when root edits a file directly,
which is exactly how "root starts modifying code" usually looks. This module
extends the same reused-hook approach to the already-registered
`PreToolUse`/`Write` and `PreToolUse`/`Edit` hooks
(`pre_write_handler.handle_pre_write`), reusing
`root_activation_context.build_root_write_mode_select_context`.

Targeted tests only (not the full install matrix): (1) the reminder fires on
a pertinent (nWave-adjacent) Write/Edit, (2) it stays silent for
non-pertinent targets (telemetry, out-of-tree files), (3) the wiring stays
fail-open and never touches the block path, (4) HOOK_EVENTS/Agent/
SubagentStart obligations are untouched.
"""

from __future__ import annotations

from pathlib import Path

from des.adapters.drivers.hooks.root_activation_context import (
    ROOT_MODE_SELECT_REMINDER,
    build_root_write_mode_select_context,
    is_nwave_adjacent_write,
)


REPO = Path(__file__).resolve().parents[2]
PRE_WRITE_HANDLER_PATH = REPO / "src/des/adapters/drivers/hooks/pre_write_handler.py"
HOOK_DEFINITIONS_PATH = REPO / "scripts/shared/hook_definitions.py"


# --- 1. reminder fires on a pertinent Write/Edit ----------------------------


def test_reminder_fires_on_nwave_adjacent_write_with_no_active_session() -> None:
    context = build_root_write_mode_select_context(
        file_path="/repo/src/des/domain/foo.py", session_active=False
    )
    assert context == ROOT_MODE_SELECT_REMINDER


def test_is_nwave_adjacent_write_true_for_all_non_bookkeeping_paths() -> None:
    """K4 root-write-boundary: pertinence is no longer restricted to a fixed
    root allowlist -- any non-`.nwave` path is pertinent after activation,
    including recognized project roots, generated-plan artifacts, docs, and
    arbitrary top-level packages."""
    assert is_nwave_adjacent_write("/repo/src/des/domain/foo.py") is True
    assert is_nwave_adjacent_write("/repo/nWave/skills/nw-mode-select/SKILL.md") is True
    assert is_nwave_adjacent_write("/repo/tests/nwave_ai/test_x.py") is True
    assert is_nwave_adjacent_write("/repo/scripts/shared/hook_definitions.py") is True
    assert is_nwave_adjacent_write("/repo/hc/generated_plan.py") is True
    assert is_nwave_adjacent_write("/repo/docs/notes.md") is True
    assert is_nwave_adjacent_write("/repo/some_arbitrary_package/mod.py") is True


# --- 2. no reminder for non-pertinent targets -------------------------------


def test_no_reminder_for_telemetry_path() -> None:
    assert (
        build_root_write_mode_select_context(
            file_path="/repo/.nwave/telemetry/examine/demo.jsonl",
            session_active=False,
        )
        is None
    )
    assert is_nwave_adjacent_write("/repo/.nwave/telemetry/examine/demo.jsonl") is False


def test_no_reminder_for_tests_nwave_session_bookkeeping() -> None:
    assert (
        build_root_write_mode_select_context(
            file_path="/repo/tests/.nwave/des/deliver-session.json",
            session_active=False,
        )
        is None
    )
    assert (
        is_nwave_adjacent_write("/repo/tests/.nwave/des/deliver-session.json") is False
    )


def test_reminder_fires_for_out_of_tree_file() -> None:
    """K4 root-write-boundary: pertinence is no longer scoped to a fixed
    root allowlist, so a path outside any recognised project root is now
    pertinent too -- only `.nwave/**` and a missing `file_path` stay silent."""
    assert (
        build_root_write_mode_select_context(
            file_path="/tmp/scratch/notes.txt", session_active=False
        )
        == ROOT_MODE_SELECT_REMINDER
    )


def test_no_reminder_when_deliver_session_already_active() -> None:
    """A live deliver session means mode is already engaged elsewhere."""
    assert (
        build_root_write_mode_select_context(
            file_path="/repo/src/des/domain/foo.py", session_active=True
        )
        is None
    )


def test_no_reminder_for_missing_file_path() -> None:
    assert (
        build_root_write_mode_select_context(file_path="", session_active=False) is None
    )
    assert (
        build_root_write_mode_select_context(file_path=None, session_active=False)
        is None
    )


# --- 3. fail-open + block path untouched ------------------------------------


def test_root_write_activation_wired_only_in_allow_branch_try_except() -> None:
    """The reminder call is wrapped in its own try/except (best-effort) and
    lives after the guard's block branch, never inside it."""
    source = PRE_WRITE_HANDLER_PATH.read_text(encoding="utf-8")
    else_idx = source.index("else:\n                # Determine allow reason")
    allow_branch = source[else_idx:]
    assert "build_root_write_mode_select_context" in allow_branch
    assert "try:" in allow_branch
    assert "except Exception:" in allow_branch


def test_pre_write_block_branch_does_not_reference_root_activation() -> None:
    """The `guard_result.blocked` branch must stay untouched by K3-A."""
    source = PRE_WRITE_HANDLER_PATH.read_text(encoding="utf-8")
    blocked_idx = source.index("if guard_result.blocked:")
    else_idx = source.index("else:\n                # Determine allow reason")
    blocked_branch = source[blocked_idx:else_idx]
    assert "build_root_write_mode_select_context" not in blocked_branch


# --- 4. no new hook event registered ----------------------------------------


def test_no_new_hook_event_registered_for_k3a_write_activation() -> None:
    source = HOOK_DEFINITIONS_PATH.read_text(encoding="utf-8")
    assert "SessionStart" not in source
    assert "UserPromptSubmit" not in source
    assert (
        'HookEvent(event="PreToolUse", matcher="Write", action="pre-write", is_guard=True)'
        in source
    )
    assert (
        'HookEvent(event="PreToolUse", matcher="Edit", action="pre-edit", is_guard=True)'
        in source
    )
