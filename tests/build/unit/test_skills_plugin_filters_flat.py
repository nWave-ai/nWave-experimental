"""Acceptance test: SkillsPlugin filters private skills in flat layout.

Step 02-01: Migrate skills_plugin.py to shared skill_distribution module.
Latent bug fix: _install_new_flat() did NOT filter private skills.

Driving port: SkillsPlugin.install()
Test Budget: 1 acceptance test (bug fix verification)
"""

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.skills_plugin import SkillsPlugin


@pytest.fixture
def logger() -> logging.Logger:
    return logging.getLogger("test.skills-filter-flat")


@pytest.fixture
def claude_dir(tmp_path: Path) -> Path:
    d = tmp_path / ".claude"
    d.mkdir()
    return d


@pytest.fixture
def flat_source_with_private(tmp_path: Path) -> Path:
    """Source with 3 public skills and 1 private skill in flat layout."""
    source = tmp_path / "source" / "skills"
    source.mkdir(parents=True)
    for name in ("nw-tdd-methodology", "nw-hexagonal-testing", "nw-quality-framework"):
        d = source / name
        d.mkdir()
        (d / "SKILL.md").write_text(f"# {name}\nContent.\n", encoding="utf-8")
    # Private skill: owned only by a private agent
    private = source / "nw-private-internal"
    private.mkdir()
    (private / "SKILL.md").write_text("# Private\nSecret.\n", encoding="utf-8")
    return source


class TestFlatLayoutFiltersPrivateSkills:
    """SkillsPlugin.install() with flat layout excludes private skills."""

    def test_private_skill_not_installed_in_flat_layout(
        self,
        claude_dir: Path,
        flat_source_with_private: Path,
        logger: logging.Logger,
    ) -> None:
        """Given a flat source with 3 public and 1 private skill,
        When SkillsPlugin.install() runs with filtering enabled,
        Then only the 3 public skills are installed,
        And the private skill directory does NOT exist in the target.
        """
        public_agents = {"software-crafter", "solution-architect"}
        ownership_map = {
            "nw-tdd-methodology": {"software-crafter"},
            "nw-hexagonal-testing": {"software-crafter"},
            "nw-quality-framework": {"software-crafter"},
            "nw-private-internal": {"private-agent"},
        }

        context = InstallContext(
            claude_dir=claude_dir,
            scripts_dir=Path("/tmp/scripts"),
            templates_dir=Path("/tmp/templates"),
            logger=logger,
            project_root=flat_source_with_private.parent,
            framework_source=flat_source_with_private.parent,
        )

        # Mock at the skills_plugin module boundary: control what
        # load_public_agents and build_ownership_map return.
        # These are port-boundary mocks -- the actual agent_catalog reads
        # YAML files from disk which we don't have in test.
        with (
            patch(
                "scripts.install.plugins.skills_plugin.load_public_agents",
                return_value=public_agents,
            ),
            patch(
                "scripts.install.plugins.skills_plugin.build_ownership_map",
                return_value=ownership_map,
            ),
        ):
            plugin = SkillsPlugin()
            result = plugin.install(context)

        assert result.success, f"Installation failed: {result.message}"

        skills_target = claude_dir / "skills"

        # Public skills MUST be installed
        assert (skills_target / "nw-tdd-methodology" / "SKILL.md").exists()
        assert (skills_target / "nw-hexagonal-testing" / "SKILL.md").exists()
        assert (skills_target / "nw-quality-framework" / "SKILL.md").exists()

        # Private skill MUST NOT be installed (latent bug fix)
        assert not (skills_target / "nw-private-internal").exists(), (
            "Private skill 'nw-private-internal' should NOT be installed in flat layout"
        )
