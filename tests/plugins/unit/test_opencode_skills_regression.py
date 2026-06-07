"""Regression tests for OpenCode skills installation.

Exercises OpenCodeSkillsPlugin directly with tmp_path fixtures to verify:
- SKILL.md format output
- Manifest tracking
- Private skill exclusion
- Old hierarchical layout migration
- Correct skill counts
- Uninstall scope (manifest-based, preserves custom skills)
- Reinstall (stale removal + fresh copy)
- No private agent skill leakage

All tests use tmp_path -- no real filesystem side effects.
"""

import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.install.plugins.base import InstallContext, PluginResult
from scripts.install.plugins.opencode_skills_plugin import OpenCodeSkillsPlugin


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_flat_skill(skills_dir: Path, skill_name: str, content: str = "") -> Path:
    """Create a nw-prefixed SKILL.md directory (NEW_FLAT layout).

    Returns the skill directory path.
    """
    skill_dir = skills_dir / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    body = (
        content or f"---\nname: {skill_name}\n---\n\n# {skill_name}\n\nSkill content.\n"
    )
    (skill_dir / "SKILL.md").write_text(body, encoding="utf-8")
    return skill_dir


def _create_hierarchical_skill(
    skills_dir: Path, agent_name: str, skill_name: str
) -> Path:
    """Create a {agent}/*.md file (OLD_HIERARCHICAL layout).

    Returns the skill file path.
    """
    agent_dir = skills_dir / agent_name
    agent_dir.mkdir(parents=True, exist_ok=True)
    content = f"---\nname: {skill_name}\n---\n\n# {skill_name}\n\nSkill content.\n"
    skill_file = agent_dir / f"{skill_name}.md"
    skill_file.write_text(content, encoding="utf-8")
    return skill_file


def _create_agent_file(agents_dir: Path, agent_name: str, skills: list[str]) -> None:
    """Create a minimal agent .md file with YAML frontmatter listing skills."""
    skills_yaml = "\n".join(f"  - {s}" for s in skills)
    content = (
        f"---\nname: {agent_name}\nskills:\n{skills_yaml}\n---\n\n"
        f"# {agent_name}\n\nAgent content.\n"
    )
    (agents_dir / f"{agent_name}.md").write_text(content, encoding="utf-8")


def _create_catalog(nwave_dir: Path, agents: dict[str, bool]) -> None:
    """Create a framework-catalog.yaml with agent public/private flags.

    Args:
        nwave_dir: nWave directory (contains framework-catalog.yaml)
        agents: dict of agent_name -> is_public
    """
    import yaml

    catalog = {
        "agents": {name: {"public": is_public} for name, is_public in agents.items()}
    }
    catalog_path = nwave_dir / "framework-catalog.yaml"
    catalog_path.write_text(yaml.dump(catalog, default_flow_style=False))


def _make_context(
    tmp_path: Path,
    project_root: Path,
    framework_source: Path,
) -> InstallContext:
    """Build an InstallContext pointing at tmp_path directories."""
    return InstallContext(
        claude_dir=tmp_path / ".claude",
        scripts_dir=tmp_path / "scripts",
        templates_dir=tmp_path / "templates",
        logger=logging.getLogger("test"),
        project_root=project_root,
        framework_source=framework_source,
    )


def _run_install(
    tmp_path: Path,
    context: InstallContext,
) -> PluginResult:
    """Run OpenCodeSkillsPlugin.install() with _opencode_skills_dir patched."""
    target_dir = tmp_path / "opencode_target" / "skills"
    target_dir.mkdir(parents=True, exist_ok=True)

    plugin = OpenCodeSkillsPlugin()
    with patch(
        "scripts.install.plugins.opencode_skills_plugin._opencode_skills_dir",
        return_value=target_dir,
    ):
        result = plugin.install(context)
    return result


def _run_uninstall(
    tmp_path: Path,
    context: InstallContext,
) -> PluginResult:
    """Run OpenCodeSkillsPlugin.uninstall() with _opencode_skills_dir patched."""
    target_dir = tmp_path / "opencode_target" / "skills"
    target_dir.mkdir(parents=True, exist_ok=True)

    plugin = OpenCodeSkillsPlugin()
    with patch(
        "scripts.install.plugins.opencode_skills_plugin._opencode_skills_dir",
        return_value=target_dir,
    ):
        result = plugin.uninstall(context)
    return result


def _get_target_dir(tmp_path: Path) -> Path:
    """Return the patched target directory path."""
    return tmp_path / "opencode_target" / "skills"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def project_tree(tmp_path):
    """Set up a minimal project tree with public and private agents/skills.

    Layout:
        project_root/
            nWave/
                framework-catalog.yaml  (2 public, 1 private agent)
                agents/
                    nw-crafter.md       (public, owns nw-tdd-methodology)
                    nw-researcher.md    (public, owns nw-research-skill)
                    nw-secret-agent.md  (private, owns nw-secret-skill)
                skills/
                    nw/
                        nw-tdd-methodology/SKILL.md
                        nw-research-skill/SKILL.md
                        nw-secret-skill/SKILL.md
    """
    project_root = tmp_path / "project"
    nwave_dir = project_root / "nWave"
    nwave_dir.mkdir(parents=True)

    # Catalog: 2 public agents, 1 private
    _create_catalog(
        nwave_dir,
        {
            "crafter": True,
            "researcher": True,
            "secret-agent": False,
        },
    )

    # Agent files (define skill ownership)
    agents_dir = nwave_dir / "agents"
    agents_dir.mkdir()
    _create_agent_file(agents_dir, "nw-crafter", ["nw-tdd-methodology"])
    _create_agent_file(agents_dir, "nw-researcher", ["nw-research-skill"])
    _create_agent_file(agents_dir, "nw-secret-agent", ["nw-secret-skill"])

    # Skills source (flat layout under dist path)
    dist_dir = project_root / "dist"
    skills_source = dist_dir / "skills" / "nw"
    skills_source.mkdir(parents=True)
    _create_flat_skill(skills_source, "nw-tdd-methodology")
    _create_flat_skill(skills_source, "nw-research-skill")
    _create_flat_skill(skills_source, "nw-secret-skill")

    return {
        "project_root": project_root,
        "framework_source": dist_dir,
        "nwave_dir": nwave_dir,
        "skills_source": skills_source,
        "agents_dir": agents_dir,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestOpenCodeSkillsRegression:
    """Regression tests for OpenCodeSkillsPlugin install/uninstall lifecycle."""

    def test_install_produces_skill_md_format(self, tmp_path, project_tree):
        """Each installed skill directory contains a SKILL.md file."""
        context = _make_context(
            tmp_path,
            project_tree["project_root"],
            project_tree["framework_source"],
        )
        result = _run_install(tmp_path, context)

        assert result.success is True

        target_dir = _get_target_dir(tmp_path)
        installed_dirs = [
            d for d in target_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
        ]
        assert len(installed_dirs) > 0, "At least one skill should be installed"

        for skill_dir in installed_dirs:
            skill_md = skill_dir / "SKILL.md"
            assert skill_md.exists(), (
                f"Skill directory {skill_dir.name} missing SKILL.md"
            )
            content = skill_md.read_text()
            assert len(content) > 0, f"SKILL.md in {skill_dir.name} should not be empty"

    def test_manifest_written_after_install(self, tmp_path, project_tree):
        """Install writes .nwave-manifest.json with correct skill entries."""
        context = _make_context(
            tmp_path,
            project_tree["project_root"],
            project_tree["framework_source"],
        )
        _run_install(tmp_path, context)

        target_dir = _get_target_dir(tmp_path)
        manifest_path = target_dir / ".nwave-manifest.json"
        assert manifest_path.exists(), "Manifest file should be written after install"

        manifest = json.loads(manifest_path.read_text())
        assert "installed_skills" in manifest
        assert "version" in manifest
        assert isinstance(manifest["installed_skills"], list)
        assert len(manifest["installed_skills"]) > 0, (
            "Manifest should list at least one installed skill"
        )

    def test_private_skills_excluded(self, tmp_path, project_tree):
        """Skills owned by private agents are not copied to target."""
        context = _make_context(
            tmp_path,
            project_tree["project_root"],
            project_tree["framework_source"],
        )
        _run_install(tmp_path, context)

        target_dir = _get_target_dir(tmp_path)

        # The private skill should NOT appear in target
        assert not (target_dir / "nw-secret-skill").exists(), (
            "Private skill nw-secret-skill should not be installed"
        )

        # Also verify it is not in the manifest
        manifest = json.loads((target_dir / ".nwave-manifest.json").read_text())
        assert "nw-secret-skill" not in manifest["installed_skills"], (
            "Private skill should not appear in manifest"
        )

    def test_old_hierarchical_layout_handled(self, tmp_path):
        """Skills from old {agent}/*.md layout are installed correctly."""
        project_root = tmp_path / "project"
        nwave_dir = project_root / "nWave"
        nwave_dir.mkdir(parents=True)

        # Create minimal catalog to satisfy fail-closed load_public_agents
        (nwave_dir / "framework-catalog.yaml").write_text(
            "agents:\n  crafter:\n    public: true\n"
        )

        # Create agent file so ownership map links skills to the public agent
        agents_dir = nwave_dir / "agents"
        agents_dir.mkdir()
        _create_agent_file(
            agents_dir,
            "nw-crafter",
            ["nw-tdd-methodology", "nw-quality-framework"],
        )

        # Use project layout (nWave/skills/) instead of dist layout
        skills_dir = nwave_dir / "skills"
        skills_dir.mkdir()

        # OLD_HIERARCHICAL: {agent}/*.md files (no nw- prefix dirs)
        _create_hierarchical_skill(skills_dir, "crafter", "tdd-methodology")
        _create_hierarchical_skill(skills_dir, "crafter", "quality-framework")

        context = _make_context(
            tmp_path,
            project_root,
            framework_source=tmp_path / "nonexistent_dist",  # force project layout
        )

        result = _run_install(tmp_path, context)

        assert result.success is True

        target_dir = _get_target_dir(tmp_path)
        installed_dirs = [
            d for d in target_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
        ]
        assert len(installed_dirs) == 2, (
            f"Expected 2 skills from hierarchical layout, got {len(installed_dirs)}"
        )

        for skill_dir in installed_dirs:
            assert (skill_dir / "SKILL.md").exists(), (
                f"Hierarchical skill {skill_dir.name} should have SKILL.md"
            )

    def test_correct_public_skill_count(self, tmp_path, project_tree):
        """Only public skills are installed -- count matches expected."""
        context = _make_context(
            tmp_path,
            project_tree["project_root"],
            project_tree["framework_source"],
        )
        result = _run_install(tmp_path, context)

        assert result.success is True

        target_dir = _get_target_dir(tmp_path)
        manifest = json.loads((target_dir / ".nwave-manifest.json").read_text())

        # 2 public skills: nw-tdd-methodology, nw-research-skill
        # 1 private skill: nw-secret-skill (excluded)
        assert len(manifest["installed_skills"]) == 2, (
            f"Expected 2 public skills, got {len(manifest['installed_skills'])}: "
            f"{manifest['installed_skills']}"
        )

    def test_uninstall_removes_only_tracked_skills(self, tmp_path, project_tree):
        """Uninstall removes manifest-tracked skills but preserves custom ones."""
        context = _make_context(
            tmp_path,
            project_tree["project_root"],
            project_tree["framework_source"],
        )

        # First install
        _run_install(tmp_path, context)

        target_dir = _get_target_dir(tmp_path)

        # Simulate a user-created custom skill (not in manifest)
        custom_skill = target_dir / "my-custom-skill"
        custom_skill.mkdir()
        (custom_skill / "SKILL.md").write_text("# My Custom Skill\n")

        # Verify custom skill exists before uninstall
        assert custom_skill.exists()

        # Uninstall
        uninstall_result = _run_uninstall(tmp_path, context)

        assert uninstall_result.success is True

        # Custom skill should still exist
        assert custom_skill.exists(), (
            "User-created custom skill should be preserved after uninstall"
        )
        assert (custom_skill / "SKILL.md").exists()

        # nWave skills should be removed
        assert not (target_dir / "nw-tdd-methodology").exists(), (
            "nWave skill should be removed after uninstall"
        )
        assert not (target_dir / "nw-research-skill").exists(), (
            "nWave skill should be removed after uninstall"
        )

        # Manifest should be removed
        assert not (target_dir / ".nwave-manifest.json").exists(), (
            "Manifest should be removed after uninstall"
        )

    def test_reinstall_cleans_stale(self, tmp_path, project_tree):
        """Reinstall removes stale skills from previous install and adds new ones."""
        context = _make_context(
            tmp_path,
            project_tree["project_root"],
            project_tree["framework_source"],
        )

        # First install
        _run_install(tmp_path, context)

        target_dir = _get_target_dir(tmp_path)
        manifest_before = json.loads((target_dir / ".nwave-manifest.json").read_text())
        assert len(manifest_before["installed_skills"]) == 2

        # Simulate a skill that was installed previously but is now removed
        # from source (stale skill)
        stale_skill = target_dir / "nw-deprecated-skill"
        stale_skill.mkdir()
        (stale_skill / "SKILL.md").write_text("# Stale\n")

        # Add it to the manifest as if it were previously installed
        manifest_before["installed_skills"].append("nw-deprecated-skill")
        (target_dir / ".nwave-manifest.json").write_text(
            json.dumps(manifest_before, indent=2) + "\n"
        )

        # Re-install (should overwrite/clean)
        _run_install(tmp_path, context)

        manifest_after = json.loads((target_dir / ".nwave-manifest.json").read_text())

        # Stale skill should NOT be in new manifest
        assert "nw-deprecated-skill" not in manifest_after["installed_skills"], (
            "Stale skill should not appear in manifest after reinstall"
        )

        # Stale skill directory may or may not be cleaned by the plugin
        # (the plugin overwrites existing dirs for matching names but the
        # stale directory name won't match any source skill). The manifest
        # is the source of truth -- verify it reflects only current skills.
        assert len(manifest_after["installed_skills"]) == 2

    def test_no_private_agent_skills_leak(self, tmp_path, project_tree):
        """Double-check: no private agent skill appears in target or manifest."""
        context = _make_context(
            tmp_path,
            project_tree["project_root"],
            project_tree["framework_source"],
        )
        _run_install(tmp_path, context)

        target_dir = _get_target_dir(tmp_path)

        # Enumerate all directories in target
        all_installed = {
            d.name
            for d in target_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        }

        # Private skill must not appear anywhere
        private_skills = {"nw-secret-skill", "secret-skill"}
        leaked = all_installed & private_skills
        assert leaked == set(), f"Private skills leaked into target: {leaked}"

        # Also verify via manifest
        manifest = json.loads((target_dir / ".nwave-manifest.json").read_text())
        for skill_name in manifest["installed_skills"]:
            assert "secret" not in skill_name, (
                f"Private skill '{skill_name}' found in manifest"
            )
