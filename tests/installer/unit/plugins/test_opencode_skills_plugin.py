"""Unit tests for OpenCode skills installer plugin.

Tests validate that:
- install() transforms nWave skills into OpenCode SKILL.md format
- install() prefixes duplicate skill names with their agent group name
- install() preserves file content (frontmatter + body) exactly
- verify() checks that installed SKILL.md files exist with valid frontmatter
- uninstall() only removes skills listed in the manifest, not user-created skills
- install() creates a manifest file tracking installed skill names

CRITICAL: Tests follow hexagonal architecture - mocks only at port boundaries.
"""

import json
from unittest.mock import MagicMock

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.opencode_skills_plugin import OpenCodeSkillsPlugin


def _make_context(tmp_path):
    """Create an InstallContext with a minimal skill source layout.

    Returns:
        Tuple of (context, skills_source, opencode_skills_target)
    """
    project_root = tmp_path / "project"
    framework_source = tmp_path / "framework"

    skills_source = project_root / "nWave" / "skills"
    skills_source.mkdir(parents=True)

    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)

    logger = MagicMock()

    context = InstallContext(
        claude_dir=claude_dir,
        scripts_dir=tmp_path / "scripts",
        templates_dir=tmp_path / "templates",
        logger=logger,
        project_root=project_root,
        framework_source=framework_source,
    )

    opencode_skills_target = tmp_path / "home" / ".config" / "opencode" / "skills"

    return context, skills_source, opencode_skills_target


def _create_skill(skills_source, agent_name, skill_name, content=None):
    """Create a skill .md file in the source layout.

    Args:
        skills_source: Path to nWave/skills/ directory
        agent_name: Agent group name (e.g. 'software-crafter')
        skill_name: Skill name without extension (e.g. 'tdd-methodology')
        content: Optional content; if None, generates default frontmatter + body
    """
    agent_dir = skills_source / agent_name
    agent_dir.mkdir(parents=True, exist_ok=True)

    if content is None:
        content = (
            f"---\n"
            f"name: {skill_name}\n"
            f"description: {skill_name} description for {agent_name}\n"
            f"---\n"
            f"\n"
            f"# {skill_name}\n"
            f"\n"
            f"Content for {skill_name} in {agent_name}.\n"
        )

    (agent_dir / f"{skill_name}.md").write_text(content)


class TestInstallTransformsSkillToOpenCodeFormat:
    """Test that install() creates {skill-name}/SKILL.md structure."""

    def test_install_transforms_skill_to_opencode_format(self, tmp_path, monkeypatch):
        """
        GIVEN: A source skill at software-crafter/tdd-methodology.md
        WHEN: install() is called
        THEN: The skill appears as tdd-methodology/SKILL.md in the target
        """
        context, skills_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_skills_plugin._opencode_skills_dir",
            lambda: target,
        )

        _create_skill(skills_source, "software-crafter", "tdd-methodology")

        plugin = OpenCodeSkillsPlugin()
        result = plugin.install(context)

        assert result.success is True
        skill_md = target / "tdd-methodology" / "SKILL.md"
        assert skill_md.exists(), f"Expected {skill_md} to exist"


class TestInstallPrefixesDuplicateSkillNames:
    """Test that install() prefixes colliding skill names with agent group."""

    def test_install_prefixes_duplicate_skill_names(self, tmp_path, monkeypatch):
        """
        GIVEN: Two skills with the same name in different agent groups
               (software-crafter/critique-dimensions.md and
                agent-builder/critique-dimensions.md)
        WHEN: install() is called
        THEN: Both appear with agent-prefixed names:
              software-crafter-critique-dimensions/SKILL.md
              agent-builder-critique-dimensions/SKILL.md
        """
        context, skills_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_skills_plugin._opencode_skills_dir",
            lambda: target,
        )

        _create_skill(skills_source, "software-crafter", "critique-dimensions")
        _create_skill(skills_source, "agent-builder", "critique-dimensions")

        plugin = OpenCodeSkillsPlugin()
        result = plugin.install(context)

        assert result.success is True

        sc_skill = target / "software-crafter-critique-dimensions" / "SKILL.md"
        ab_skill = target / "agent-builder-critique-dimensions" / "SKILL.md"

        assert sc_skill.exists(), f"Expected {sc_skill} to exist"
        assert ab_skill.exists(), f"Expected {ab_skill} to exist"

        # The un-prefixed name should NOT exist
        bare_skill = target / "critique-dimensions" / "SKILL.md"
        assert not bare_skill.exists(), "Bare name should not exist for duplicates"

        # Frontmatter name: must match the prefixed directory name
        sc_content = sc_skill.read_text()
        assert "name: software-crafter-critique-dimensions" in sc_content
        ab_content = ab_skill.read_text()
        assert "name: agent-builder-critique-dimensions" in ab_content


class TestInstallPreservesFrontmatter:
    """Test that install() copies file content without modification."""

    def test_install_preserves_frontmatter(self, tmp_path, monkeypatch):
        """
        GIVEN: A source skill file with frontmatter and body content
        WHEN: install() transforms it to SKILL.md
        THEN: The SKILL.md content is byte-for-byte identical to the source
        """
        context, skills_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_skills_plugin._opencode_skills_dir",
            lambda: target,
        )

        original_content = (
            "---\n"
            "name: tdd-methodology\n"
            "description: Deep knowledge for Outside-In TDD\n"
            "---\n"
            "\n"
            "# Outside-In TDD Methodology\n"
            "\n"
            "## Double-Loop TDD Architecture\n"
            "\n"
            "Outer loop: ATDD/E2E Tests.\n"
        )

        _create_skill(
            skills_source, "software-crafter", "tdd-methodology", original_content
        )

        plugin = OpenCodeSkillsPlugin()
        plugin.install(context)

        installed_content = (target / "tdd-methodology" / "SKILL.md").read_text()
        assert installed_content == original_content


class TestVerifyChecksSkillMdExists:
    """Test that verify() validates SKILL.md presence in installed skills."""

    def test_verify_checks_skill_md_exists(self, tmp_path, monkeypatch):
        """
        GIVEN: Skills installed with valid SKILL.md files and a manifest
        WHEN: verify() is called
        THEN: Verification passes
        """
        context, _skills_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_skills_plugin._opencode_skills_dir",
            lambda: target,
        )

        # Create installed skill structure directly
        skill_dir = target / "tdd-methodology"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: tdd-methodology\ndescription: test\n---\n\n# Test\n"
        )

        # Create manifest
        manifest = {"installed_skills": ["tdd-methodology"], "version": "1.0"}
        (target / ".nwave-manifest.json").write_text(json.dumps(manifest))

        plugin = OpenCodeSkillsPlugin()
        result = plugin.verify(context)

        assert result.success is True

    def test_verify_fails_when_skill_md_missing(self, tmp_path, monkeypatch):
        """
        GIVEN: A skill directory exists but SKILL.md is missing
        WHEN: verify() is called
        THEN: Verification fails with an error
        """
        context, _skills_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_skills_plugin._opencode_skills_dir",
            lambda: target,
        )

        # Create directory without SKILL.md
        skill_dir = target / "tdd-methodology"
        skill_dir.mkdir(parents=True)

        # Create manifest referencing this skill
        manifest = {"installed_skills": ["tdd-methodology"], "version": "1.0"}
        (target / ".nwave-manifest.json").write_text(json.dumps(manifest))

        plugin = OpenCodeSkillsPlugin()
        result = plugin.verify(context)

        assert result.success is False
        assert any("tdd-methodology" in e for e in result.errors)


class TestUninstallRemovesOnlyNwaveSkills:
    """Test that uninstall() only removes manifest-tracked skills."""

    def test_uninstall_removes_only_nwave_skills(self, tmp_path, monkeypatch):
        """
        GIVEN: An OpenCode skills directory with both nWave-installed and
               user-created skills
        WHEN: uninstall() is called
        THEN: Only nWave-installed skills (listed in manifest) are removed;
              user-created skills remain untouched
        """
        context, _skills_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_skills_plugin._opencode_skills_dir",
            lambda: target,
        )

        # Create nWave-installed skill
        nwave_skill = target / "tdd-methodology"
        nwave_skill.mkdir(parents=True)
        (nwave_skill / "SKILL.md").write_text("---\nname: tdd-methodology\n---\n")

        # Create user-owned skill (NOT in manifest)
        user_skill = target / "my-custom-skill"
        user_skill.mkdir(parents=True)
        (user_skill / "SKILL.md").write_text("---\nname: my-custom-skill\n---\n")

        # Manifest only tracks nWave skills
        manifest = {"installed_skills": ["tdd-methodology"], "version": "1.0"}
        (target / ".nwave-manifest.json").write_text(json.dumps(manifest))

        plugin = OpenCodeSkillsPlugin()
        result = plugin.uninstall(context)

        assert result.success is True

        # nWave skill should be removed
        assert not nwave_skill.exists(), "nWave skill should be removed"

        # User skill should remain
        assert user_skill.exists(), "User-created skill must remain untouched"
        assert (user_skill / "SKILL.md").exists()

    def test_uninstall_removes_manifest(self, tmp_path, monkeypatch):
        """
        GIVEN: An OpenCode skills directory with a manifest
        WHEN: uninstall() is called
        THEN: The manifest file is also removed
        """
        context, _skills_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_skills_plugin._opencode_skills_dir",
            lambda: target,
        )

        target.mkdir(parents=True, exist_ok=True)
        manifest_path = target / ".nwave-manifest.json"
        manifest_path.write_text(json.dumps({"installed_skills": [], "version": "1.0"}))

        plugin = OpenCodeSkillsPlugin()
        plugin.uninstall(context)

        assert not manifest_path.exists(), "Manifest should be removed after uninstall"


class TestInstallCreatesManifest:
    """Test that install() creates a manifest tracking installed skills."""

    def test_install_creates_manifest(self, tmp_path, monkeypatch):
        """
        GIVEN: Multiple source skills across agent groups
        WHEN: install() is called
        THEN: A .nwave-manifest.json is created listing all installed skill names
        """
        context, skills_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_skills_plugin._opencode_skills_dir",
            lambda: target,
        )

        _create_skill(skills_source, "software-crafter", "tdd-methodology")
        _create_skill(skills_source, "software-crafter", "quality-framework")
        _create_skill(skills_source, "acceptance-designer", "bdd-methodology")

        plugin = OpenCodeSkillsPlugin()
        plugin.install(context)

        manifest_path = target / ".nwave-manifest.json"
        assert manifest_path.exists(), "Manifest should be created"

        manifest = json.loads(manifest_path.read_text())
        assert "installed_skills" in manifest
        assert sorted(manifest["installed_skills"]) == sorted(
            ["tdd-methodology", "quality-framework", "bdd-methodology"]
        )

    def test_install_manifest_includes_prefixed_names_for_duplicates(
        self, tmp_path, monkeypatch
    ):
        """
        GIVEN: Skills with duplicate names across agent groups
        WHEN: install() is called
        THEN: The manifest lists the prefixed names, not the bare names
        """
        context, skills_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_skills_plugin._opencode_skills_dir",
            lambda: target,
        )

        _create_skill(skills_source, "software-crafter", "critique-dimensions")
        _create_skill(skills_source, "agent-builder", "critique-dimensions")
        _create_skill(skills_source, "software-crafter", "tdd-methodology")

        plugin = OpenCodeSkillsPlugin()
        plugin.install(context)

        manifest = json.loads((target / ".nwave-manifest.json").read_text())
        installed = sorted(manifest["installed_skills"])

        assert installed == sorted(
            [
                "agent-builder-critique-dimensions",
                "software-crafter-critique-dimensions",
                "tdd-methodology",
            ]
        )
