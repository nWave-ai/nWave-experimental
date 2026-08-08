"""activation-routing-before-mutation: nw-bugfix wires nw-mode-select as its
first step, and stops hardcoding `~/.claude`-relative skill paths.

Prior evidence, corroborated by the Haiku review of the same commit, showed a neutral M-shaped
bugfix task reaching `Skill(nw-bugfix)` via the generated project CLAUDE.md
before any hook fired, but never producing an explicit S/M/L classification —
`nw-mode-select` was never referenced by nw-bugfix itself, only reachable
reactively through the SubagentStart/PreToolUse hook reminders, which fire
only once a mutation is already in flight (or not at all, on the CLAUDE.md-
only activation path exercised at t=0).

nw-bugfix also carried three `~/.claude/skills/nw-<skill>/SKILL.md` literal
path mentions describing how the troubleshooter, the charter author, and the
lane-map SSOT load their own skills -- the same D3-class defect
`root_activation_context.py` already fixed for the root reminder, reachable
here because this text is part of the skill body loaded into the
orchestrator's own context the moment `Skill(nw-bugfix)` fires.

These tests pin the successor contract: nw-mode-select is invoked as an
explicit first step (before any phase that dispatches an agent or touches the
tree), and every skill-loading mention resolves by name via the Skill tool
rather than a literal home-relative path.
"""

from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
BUGFIX_SKILL_PATH = REPO / "nWave/skills/nw-bugfix/SKILL.md"


def _text() -> str:
    return BUGFIX_SKILL_PATH.read_text(encoding="utf-8")


def test_bugfix_skill_file_exists() -> None:
    assert BUGFIX_SKILL_PATH.is_file()


def test_bugfix_invokes_mode_select_before_any_phase() -> None:
    """nw-mode-select must be named, and named BEFORE the first phase that
    dispatches an agent or touches the tree (Phase 0-worktree) -- otherwise
    classification happens after the fact, which is orientation theatre."""
    text = _text()
    assert "nw-mode-select" in text, (
        "nw-bugfix never names nw-mode-select -- classification stays "
        "reactive-only (hook reminder after first mutation), never an "
        "explicit step this skill's own procedure requires."
    )
    mode_select_index = text.index("nw-mode-select")
    worktree_index = text.index("### Phase 0-worktree")
    assert mode_select_index < worktree_index, (
        "nw-mode-select must be invoked before Phase 0-worktree (the first "
        "phase that touches the tree) -- classifying after work has already "
        "started is not orientation, it is narration."
    )


def test_bugfix_mode_select_step_names_the_skill_tool() -> None:
    """The mode-select step must direct the model to actually invoke the
    skill (Skill tool), not merely mention its name in passing prose."""
    text = _text()
    step_start = text.index("nw-mode-select")
    # The invocation instruction should be near the first mention, not a
    # stray reference buried later in unrelated prose.
    nearby = text[step_start : step_start + 400]
    assert "Skill tool" in nearby, (
        "The first nw-mode-select mention must instruct invocation via the "
        f"Skill tool. Nearby text: {nearby!r}"
    )


def test_bugfix_skill_does_not_hardcode_home_relative_skill_paths() -> None:
    """D3-analog: no `~/.claude`-relative literal path anywhere in the body
    -- invalid under an isolated CLAUDE_CONFIG_DIR, the same defect class
    already fixed in root_activation_context.py and subagent_start_handler.py.
    """
    text = _text()
    assert "~/.claude" not in text, (
        "nw-bugfix must not hardcode a ~/.claude-relative skill path; "
        "resolve every skill by name via the Skill tool instead."
    )
