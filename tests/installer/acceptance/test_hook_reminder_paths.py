"""Acceptance test: SubagentStart hook reminder resolves skills by name.

Behavioral contract (activation-routing-before-mutation, D3-analog): the
`~/.claude/skills/...` literal path this reminder used to hardcode is invalid
under any non-default `CLAUDE_CONFIG_DIR` (the isolated-install shape every
pilot arm and `nwave-ai install --target` produces) — the same defect class
`root_activation_context.py`'s D3 fix already closed for the root reminder.
This test pins the successor contract: the reminder must name skills by NAME
and point at the Skill tool as the resolution mechanism, never a literal
home-relative path.

It catches future regressions where the reminder text regains a hardcoded
path or drops the Skill-tool framing.

Given: `_build_reminder_message("nw-software-crafter")` is called
Then:  The message does NOT contain a `~/.claude/skills` literal path
And:   The message names the Skill tool as the resolution mechanism
And:   Any nw-<skill> example token named in the message is a real skill
"""

import re
from pathlib import Path

import pytest


@pytest.fixture
def mock_skills_root(tmp_path: Path) -> Path:
    """Create a realistic ~/.claude/skills/ layout with topical flat skill dirs."""
    skills_root = tmp_path / ".claude" / "skills"
    # Simulate the flat topical layout: nw-<skill-name>/SKILL.md
    topical_skills = [
        "nw-tdd-methodology",
        "nw-bdd-methodology",
        "nw-progressive-refactoring",
        "nw-hexagonal-testing",
        "nw-quality-framework",
    ]
    for skill in topical_skills:
        skill_dir = skills_root / skill
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(f"# {skill} skill\n")
    return skills_root


class TestHookReminderPathsMatchRealLayout:
    """D3-analog: hook reminder resolves skills by name, not a hardcoded path."""

    def test_reminder_does_not_hardcode_a_home_relative_skill_path(self) -> None:
        """Reminder must not hardcode `~/.claude/...` -- invalid under an
        isolated CLAUDE_CONFIG_DIR (mirrors root_activation_context.py's D3 fix).

        Given: handler is invoked for nw-software-crafter
        When:  _build_reminder_message is called
        Then:  The message does NOT contain a literal ~/.claude path
        """
        from des.adapters.drivers.hooks.subagent_start_handler import (
            _build_reminder_message,
        )

        msg = _build_reminder_message("nw-software-crafter")

        assert "~/.claude" not in msg, (
            f"Reminder must not hardcode a ~/.claude-relative path -- it is "
            f"invalid under an isolated CLAUDE_CONFIG_DIR. Got: {msg!r}"
        )

    def test_reminder_names_the_skill_tool_as_the_resolution_mechanism(self) -> None:
        """Reminder must point at the Skill tool, which resolves by name against
        whatever config dir is active -- the D3 remedy pattern already
        established for the root reminder.

        Given: handler is invoked for nw-software-crafter
        When:  _build_reminder_message is called
        Then:  The message names the Skill tool as how to load skills
        """
        from des.adapters.drivers.hooks.subagent_start_handler import (
            _build_reminder_message,
        )

        msg = _build_reminder_message("nw-software-crafter")

        assert "Skill tool" in msg, (
            f"Reminder must name the Skill tool as the resolution mechanism. "
            f"Got: {msg!r}"
        )

    def test_example_skills_listed_in_reminder_exist_in_flat_layout(
        self, mock_skills_root: Path
    ) -> None:
        """Any nw-<skill> name mentioned in the reminder must exist in skills root.

        Given: A skills root with real topical skill dirs (nw-tdd-methodology, etc.)
        When:  _build_reminder_message is called for nw-software-crafter
        Then:  Every nw-<word> token extracted from the message that looks like a
               skill name exists as a directory in the provided skills root
        """
        from des.adapters.drivers.hooks.subagent_start_handler import (
            _build_reminder_message,
        )

        msg = _build_reminder_message("nw-software-crafter")

        # Extract skill names that look like nw-<word> from the message
        # Match tokens like nw-tdd-methodology, nw-bdd-methodology
        # but NOT bare "nw-software-crafter" (that's the agent name, not a skill dir)
        skill_pattern = re.compile(r"nw-[a-z][\w-]+-[a-z][\w-]+")
        candidates = skill_pattern.findall(msg)

        # Filter out the agent type itself — we only care about skill names
        skill_candidates = [c for c in candidates if c != "nw-software-crafter"]

        for skill_name in skill_candidates:
            skill_dir = mock_skills_root / skill_name
            assert skill_dir.exists(), (
                f"Reminder references skill '{skill_name}' but "
                f"{mock_skills_root / skill_name} does not exist. "
                "If you added a new example skill to the reminder, "
                "add it to mock_skills_root fixture too, or verify "
                "it exists at ~/.claude/skills/."
            )

    def test_reminder_skill_examples_exist_in_real_installation(self) -> None:
        """Any nw-<skill> example in the reminder must exist in real ~/.claude/skills/.

        This is the production regression guard: it will fail immediately if
        the handler is updated with an example skill name that isn't installed.
        """
        from des.adapters.drivers.hooks.subagent_start_handler import (
            _build_reminder_message,
        )

        _home = Path.home()
        real_skills_root = _home / ".claude" / "skills"
        if not real_skills_root.exists():
            pytest.skip("~/.claude/skills not found — skip real-install check")

        msg = _build_reminder_message("nw-software-crafter")

        # Extract explicit nw-<skill-name> tokens (multi-word, so nw-X-Y or nw-X-Y-Z)
        skill_pattern = re.compile(r"nw-[a-z][\w-]+-[a-z][\w-]+")
        candidates = skill_pattern.findall(msg)
        skill_candidates = [c for c in candidates if c != "nw-software-crafter"]

        for skill_name in skill_candidates:
            skill_dir = real_skills_root / skill_name
            assert skill_dir.exists(), (
                f"Reminder references skill example '{skill_name}' but "
                f"{skill_dir} does not exist in real installation. "
                "Update _build_reminder_message to only reference installed skills."
            )
