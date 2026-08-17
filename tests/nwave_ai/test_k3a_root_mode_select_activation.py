"""K3-A root activation: nw-mode-select reaches the root agent, not just subs.

`subagent_start_handler.py`'s SubagentStart reminder never fires for the
root/orchestrator (only spawned sub-agents receive a SubagentStart event).
`root_activation_context.build_root_mode_select_context` closes that gap by
reusing the already-registered, already-executed `PreToolUse`/`Agent` hook
(`pre_tool_use_handler.handle_pre_tool_use`) instead of adding a new one.

These tests are targeted (not the full install matrix): they demonstrate
(1) the reminder IS produced for an nWave-adjacent dispatch, (2) it is NOT
produced for a non-pertinent one, (3) its text names the skill and the
human/auto choice without imposing ceremony, and (4) the reused
`PreToolUse` hook stays fail-open and every pre-existing hook entry is
preserved untouched.
"""

from __future__ import annotations

import ast
from pathlib import Path

from des.adapters.drivers.hooks.root_activation_context import (
    ROOT_MODE_SELECT_REMINDER,
    build_root_mode_select_context,
    is_nwave_adjacent_dispatch,
)


REPO = Path(__file__).resolve().parents[2]
PRE_TOOL_USE_HANDLER_PATH = (
    REPO / "src/des/adapters/drivers/hooks/pre_tool_use_handler.py"
)
HOOK_DEFINITIONS_PATH = REPO / "scripts/shared/hook_definitions.py"


# --- 1. context IS produced for a pertinent (nWave-adjacent) dispatch -----


def test_context_produced_for_nwave_subagent_dispatch_with_no_mode_declared() -> None:
    context = build_root_mode_select_context(
        prompt="Fix the flaky assertion in the login test.",
        subagent_type="nw-crafter",
    )
    assert context == ROOT_MODE_SELECT_REMINDER


def test_is_nwave_adjacent_dispatch_true_for_any_nw_prefixed_agent_type() -> None:
    assert is_nwave_adjacent_dispatch("nw-crafter") is True
    assert is_nwave_adjacent_dispatch("nw-mode-select") is True


# --- 2. context is NOT produced for non-pertinent requests -----------------


def test_context_absent_for_non_nwave_subagent_dispatch() -> None:
    context = build_root_mode_select_context(
        prompt="Search the web for the latest FastAPI release notes.",
        subagent_type="general-purpose",
    )
    assert context is None


def test_context_absent_when_subagent_type_missing() -> None:
    assert build_root_mode_select_context(prompt="anything", subagent_type=None) is None
    assert build_root_mode_select_context(prompt="anything", subagent_type="") is None


def test_context_absent_when_mode_already_declared_via_des_markers() -> None:
    context = build_root_mode_select_context(
        prompt="<!-- DES-WAVE: DELIVER -->\nImplement the fix.",
        subagent_type="nw-crafter",
    )
    assert context is None


def test_context_absent_when_user_already_stated_the_conversational_posture() -> None:
    context = build_root_mode_select_context(
        prompt="Just do it, direct mode, fix the typo.",
        subagent_type="nw-crafter",
    )
    assert context is None


# --- 3. text names the skill and human/auto, without imposing ceremony -----


def test_reminder_names_the_skill_path_and_human_auto_choice() -> None:
    assert "nw-mode-select" in ROOT_MODE_SELECT_REMINDER
    assert "human" in ROOT_MODE_SELECT_REMINDER
    assert "auto" in ROOT_MODE_SELECT_REMINDER


def test_reminder_stays_conditional_not_a_mandate() -> None:
    """It offers/reminds -- it must not read as a blocking imperative."""
    assert "MANDATORY" not in ROOT_MODE_SELECT_REMINDER
    assert "unless" in ROOT_MODE_SELECT_REMINDER


def test_reminder_does_not_hardcode_a_home_relative_skill_path() -> None:
    """D3 (k3a-root-activation-evidence-report.md Section 4.4): the reminder
    named a literal `~/.claude/skills/nw-mode-select/SKILL.md` path. Under any
    non-default `CLAUDE_CONFIG_DIR` -- what every isolated install produces --
    that literal path need not exist, so a model that followed it literally
    would read a missing file. The reminder must resolve the skill by NAME
    (the `Skill` tool's own resolution, which Claude Code makes
    config-dir-aware) rather than by a hardcoded filesystem path.
    """
    assert "~/.claude" not in ROOT_MODE_SELECT_REMINDER, (
        "D3: reminder must not hardcode a ~/.claude-relative path -- it fails "
        "under an isolated CLAUDE_CONFIG_DIR install"
    )
    assert "SKILL.md" not in ROOT_MODE_SELECT_REMINDER, (
        "D3: reminder must not name a literal SKILL.md path at all -- "
        "reference the skill by name so the harness resolves it"
    )


def test_reminder_names_the_skill_tool_as_the_resolution_mechanism() -> None:
    """The reminder must point at invoking the skill BY NAME (the `Skill`
    tool resolves it against whatever CLAUDE_CONFIG_DIR is active), not at a
    path the reminder-emitting hook has no way to compute correctly."""
    assert "Skill tool" in ROOT_MODE_SELECT_REMINDER


# --- 4. fail-open + hook preservation stay intact ---------------------------


def test_pre_tool_use_handler_stays_fail_open_on_exception() -> None:
    tree = ast.parse(PRE_TOOL_USE_HANDLER_PATH.read_text(encoding="utf-8"))
    func = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "handle_pre_tool_use"
    )
    source = ast.get_source_segment(
        PRE_TOOL_USE_HANDLER_PATH.read_text(encoding="utf-8"), func
    )
    assert source is not None
    assert "except Exception" in source, (
        "handle_pre_tool_use must keep its existing except Exception fail path; "
        "K3-A root activation is best-effort and must never remove it."
    )


def test_no_new_hook_event_registered_for_k3a_root_activation() -> None:
    """K3-A root activation reuses PreToolUse/Agent; HOOK_EVENTS is unchanged
    from the fixed set every other hook already relies on -- no SessionStart,
    no UserPromptSubmit, no net-new event registration."""
    source = HOOK_DEFINITIONS_PATH.read_text(encoding="utf-8")
    assert "SessionStart" not in source
    assert "UserPromptSubmit" not in source
    assert 'HookEvent(event="PreToolUse", matcher="Agent", action="pre-task")' in source
