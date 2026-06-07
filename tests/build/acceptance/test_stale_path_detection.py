"""Acceptance tests for stale command path detection and fixes.

Scenarios covered (steps 03-01 and 03-02):
  P1-01: DES recovery suggestions reference skill paths
  P1-02: Stale command path in production code detected by hook
  P1-03: Skill path references in delivery instructions are correct
  P1-04: Comment containing old path does not trigger detection

Test Budget: 4 distinct behaviors x 2 = 8 max. Using 4 tests.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# P1-01: DES recovery suggestions reference skill paths
# ---------------------------------------------------------------------------


class TestDESRecoverySuggestionsReferenceSkillPaths:
    """P1-01: DES recovery suggestions reference skill paths, not command paths."""

    STALE_PATTERN = re.compile(r"[~/.]*/commands/nw/")

    @pytest.mark.parametrize(
        "source_file",
        [
            "src/des/application/validator.py",
            "src/des/domain/des_enforcement_policy.py",
            "src/des/domain/marker_completeness_policy.py",
        ],
    )
    def test_des_recovery_suggestions_reference_skill_paths(
        self, source_file: str
    ) -> None:
        """Given DES source files, no active code references deprecated command paths."""
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        file_path = project_root / source_file
        assert file_path.exists(), f"Expected file not found: {file_path}"

        content = file_path.read_text(encoding="utf-8")
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            assert not self.STALE_PATTERN.search(line), (
                f"{source_file}:{i} references deprecated command path: {line.strip()}"
            )


# ---------------------------------------------------------------------------
# P1-03: Skill path references in delivery instructions are correct
# ---------------------------------------------------------------------------


class TestSkillPathReferencesCorrect:
    """P1-03: Skill/task files reference skill paths, not command paths."""

    STALE_PATTERN = re.compile(r"[~/.]*/commands/nw/")

    @pytest.mark.parametrize(
        "source_file",
        [
            "nWave/skills/nw-deliver/SKILL.md",
            "nWave/tasks/nw/deliver.md",
        ],
    )
    def test_skill_references_use_skill_paths(self, source_file: str) -> None:
        """Given skill/task files, no references use deprecated command path format."""
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        file_path = project_root / source_file
        assert file_path.exists(), f"Expected file not found: {file_path}"

        content = file_path.read_text(encoding="utf-8")
        for i, line in enumerate(content.splitlines(), 1):
            assert not self.STALE_PATTERN.search(line), (
                f"{source_file}:{i} references deprecated command path: {line.strip()}"
            )


# ---------------------------------------------------------------------------
# P1-02: Stale command path in production code detected by hook
# ---------------------------------------------------------------------------


class TestStalePathDetectedByHook:
    """P1-02: Stale command path in production code detected by hook."""

    def test_stale_path_in_production_code_detected(self, tmp_path: Path) -> None:
        """Given a file with stale command path, the hook detects it."""
        from scripts.hooks.check_stale_command_paths import check_files

        stale_file = tmp_path / "stale.py"
        stale_file.write_text('suggestion = "See ~/.claude/commands/nw/execute.md"\n')

        violations = check_files([stale_file])
        assert len(violations) > 0
        assert any("stale.py" in str(v) for v in violations)


# ---------------------------------------------------------------------------
# P1-04: Comment containing old path does not trigger detection
# ---------------------------------------------------------------------------


class TestCommentPathIgnored:
    """P1-04: Comment containing old path does not trigger detection."""

    def test_comment_containing_old_path_not_triggered(self, tmp_path: Path) -> None:
        """Given a file with stale path only in comments, hook passes."""
        from scripts.hooks.check_stale_command_paths import check_files

        comment_file = tmp_path / "migrated.py"
        comment_file.write_text(
            "# Migrated from ~/.claude/commands/nw/old.md to skill path\n"
            "suggestion = 'See ~/.claude/skills/nw-execute/SKILL.md'\n"
        )

        violations = check_files([comment_file])
        assert len(violations) == 0
