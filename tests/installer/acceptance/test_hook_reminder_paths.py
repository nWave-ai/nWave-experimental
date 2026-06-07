"""Acceptance test: SubagentStart hook reminder references real skill paths.

Behavioral contract (TC-4 from RCA issue #37):
  After a full install, the path pattern mentioned in the additionalContext
  for any nw-* agent must match at least one directory in ~/.claude/skills/.

This test validates OUTCOME: any path the hook mentions must be satisfiable
by the flat topical skill layout, not the old per-agent layout.

It catches future regressions where path text and filesystem diverge.

Given: A ~/.claude/skills/ directory containing at least one nw-<skill>/ dir
When:  _build_reminder_message("nw-software-crafter") is called
Then:  Every path pattern referenced in the message resolves to an existing dir
And:   The message does NOT reference the old wrong per-agent path pattern
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
    """TC-4: Hook reminder paths must be satisfiable by the installed skill layout."""

    def test_reminder_references_flat_layout_path_pattern(self) -> None:
        """Reminder message references the flat layout path, not the old per-agent path.

        Given: A skills root with topical nw-<skill>/ directories
        When:  _build_reminder_message is called for nw-software-crafter
        Then:  The message references ~/.claude/skills/nw-<skill> prefix (flat layout)
        And:   The message does NOT reference ~/.claude/skills/nw/ (old wrong layout)
        """
        from des.adapters.drivers.hooks.subagent_start_handler import (
            _build_reminder_message,
        )

        msg = _build_reminder_message("nw-software-crafter")

        # Must reference the flat layout pattern
        assert "~/.claude/skills/nw-" in msg, (
            f"Reminder must reference flat layout '~/.claude/skills/nw-<skill>' "
            f"but got: {msg!r}"
        )

    def test_reminder_does_not_reference_old_per_agent_path(self) -> None:
        """Reminder must NOT emit the old broken per-agent subdirectory path.

        Given: handler is invoked for nw-software-crafter
        When:  _build_reminder_message is called
        Then:  The message does NOT contain ~/.claude/skills/nw/nw- (old wrong path)
        """
        from des.adapters.drivers.hooks.subagent_start_handler import (
            _build_reminder_message,
        )

        msg = _build_reminder_message("nw-software-crafter")

        assert "~/.claude/skills/nw/nw-" not in msg, (
            f"Reminder must not reference old per-agent path '~/.claude/skills/nw/nw-*' "
            f"but got: {msg!r}"
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
