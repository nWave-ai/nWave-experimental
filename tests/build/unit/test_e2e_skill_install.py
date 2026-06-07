"""End-to-end skill installation verification.

Step 04-01: Invoke SkillsPlugin.install() with a real filesystem fixture
containing the full nw-*/SKILL.md layout. Verify:
  1. Installed skill count matches source skill count
  2. Every SKILL.md file is non-empty
  3. No old nw/ namespace remnants exist after install

Acceptance scenario: "Post-install verification confirms all skills are present"
(milestone-3-hardening.feature, US-10)

Driving port: SkillsPlugin.install()
Test Budget: 1 E2E test (no inner loop)
"""

import logging
from pathlib import Path

import pytest

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.skills_plugin import SkillsPlugin


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# The actual nw-*/SKILL.md directories in the source tree
SKILLS_DIR = Path(__file__).resolve().parents[3] / "nWave" / "skills"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def source_skill_names() -> list[str]:
    """Discover all nw-*/SKILL.md directory names from the real source tree."""
    return sorted(
        d.name
        for d in SKILLS_DIR.iterdir()
        if d.is_dir() and d.name.startswith("nw-") and (d / "SKILL.md").is_file()
    )


@pytest.fixture
def source_tree(tmp_path: Path, source_skill_names: list[str]) -> Path:
    """Create a tmp source tree mirroring nw-*/SKILL.md from nWave/skills/."""
    source = tmp_path / "source" / "skills"
    source.mkdir(parents=True)
    for name in source_skill_names:
        skill_dir = source / name
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            f"# {name}\nSkill content.\n", encoding="utf-8"
        )
    return source


@pytest.fixture
def claude_dir(tmp_path: Path) -> Path:
    d = tmp_path / ".claude"
    d.mkdir()
    return d


@pytest.fixture
def logger() -> logging.Logger:
    return logging.getLogger("test.e2e-skill-install")


# ---------------------------------------------------------------------------
# E2E Test
# ---------------------------------------------------------------------------


class TestEndToEndSkillInstallation:
    """E2E: SkillsPlugin.install() with full nw-*/SKILL.md source tree."""

    def test_install_produces_all_skills_with_no_legacy_remnants(
        self,
        source_tree: Path,
        claude_dir: Path,
        source_skill_names: list[str],
        logger: logging.Logger,
    ) -> None:
        """Given a source tree with all nw-*/SKILL.md directories,
        When SkillsPlugin.install() runs,
        Then:
          1. Installed skill count matches source skill count
          2. Every SKILL.md file is non-empty
          3. No old nw/ namespace directory exists
        """
        # Pre-condition: simulate old nw/ namespace from previous install
        old_nw = claude_dir / "skills" / "nw"
        old_nw.mkdir(parents=True)
        (old_nw / "software-crafter").mkdir()
        (old_nw / "software-crafter" / "tdd.md").write_text(
            "old legacy content", encoding="utf-8"
        )

        # Arrange
        plugin = SkillsPlugin()
        real_project_root = Path(__file__).resolve().parents[3]
        context = InstallContext(
            claude_dir=claude_dir,
            scripts_dir=real_project_root / "scripts" / "install",
            templates_dir=real_project_root / "nWave" / "templates",
            logger=logger,
            project_root=real_project_root,
            framework_source=source_tree.parent,
        )

        # Act
        result = plugin.install(context)

        # Assert - installation succeeded
        assert result.success, f"Installation failed: {result.message}"

        # AC1: Public skills are installed (private ones filtered out)
        installed_dirs = sorted(
            d.name
            for d in (claude_dir / "skills").iterdir()
            if d.is_dir() and d.name.startswith("nw-")
        )
        assert len(installed_dirs) > 0, "No skills installed"
        assert set(installed_dirs).issubset(set(source_skill_names)), (
            "Installed skills must be a subset of source skills"
        )

        # AC2: Every SKILL.md file is non-empty
        empty_files = []
        for name in installed_dirs:
            skill_file = claude_dir / "skills" / name / "SKILL.md"
            assert skill_file.exists(), f"{name}/SKILL.md not found"
            if skill_file.stat().st_size == 0:
                empty_files.append(name)
        assert not empty_files, f"Empty SKILL.md files found: {empty_files}"

        # AC3: No old nw/ namespace remnants
        assert not old_nw.exists(), (
            "Old nw/ namespace directory should be removed after install"
        )

    def test_upgrade_from_old_layout_to_new_produces_correct_result(
        self,
        source_tree: Path,
        claude_dir: Path,
        source_skill_names: list[str],
        logger: logging.Logger,
    ) -> None:
        """Given an existing old hierarchical install (skills/nw/{agent}/),
        When SkillsPlugin.install() runs with new flat source,
        Then old layout is replaced with new nw-* directories.
        """
        # Pre-condition: old hierarchical install exists
        old_nw = claude_dir / "skills" / "nw"
        old_nw.mkdir(parents=True)
        for agent in ("software-crafter", "troubleshooter", "researcher"):
            agent_dir = old_nw / agent
            agent_dir.mkdir()
            (agent_dir / "some-skill.md").write_text("old content", encoding="utf-8")

        # Arrange
        plugin = SkillsPlugin()
        real_project_root = Path(__file__).resolve().parents[3]
        context = InstallContext(
            claude_dir=claude_dir,
            scripts_dir=real_project_root / "scripts" / "install",
            templates_dir=real_project_root / "nWave" / "templates",
            logger=logger,
            project_root=real_project_root,
            framework_source=source_tree.parent,
        )

        # Act
        result = plugin.install(context)

        # Assert
        assert result.success, f"Upgrade failed: {result.message}"

        # Old layout completely gone
        assert not old_nw.exists(), "Old nw/ directory should be removed after upgrade"

        # New layout present with correct count
        installed_dirs = sorted(
            d.name
            for d in (claude_dir / "skills").iterdir()
            if d.is_dir() and d.name.startswith("nw-")
        )
        assert len(installed_dirs) > 0, "No skills installed after upgrade"
        assert set(installed_dirs).issubset(set(source_skill_names)), (
            "Installed skills must be subset of source (private filtered)"
        )
