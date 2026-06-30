"""AC-3 acceptance test -- OpenCode skills per-host skill-path rewrite.

Feature: installer-per-host-skill-path-portability.

A skill body referencing ~/.claude/skills/ must, after OpenCode install,
reference the OpenCode skill base (~/.config/opencode/skills/), NOT
~/.claude/skills/. The frontmatter name transform must still be correct and
the source SKILL.md on disk must be byte-unchanged.

ACTIVE-RED (atdd_pure): the opencode_skills plugin does NOT yet rewrite body
paths (design.md: "Path rewrite today: NONE (bug)") -> AssertionError.
"""

from unittest.mock import MagicMock

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.opencode_common import parse_frontmatter
from scripts.install.plugins.opencode_skills_plugin import OpenCodeSkillsPlugin


_SKILL_WITH_SKILL_PATHS = (
    "---\n"
    "name: nw-baz\n"
    "description: A skill\n"
    "user-invocable: true\n"
    "---\n"
    "\n"
    "# nw-baz\n"
    "\n"
    "Load `~/.claude/skills/nw-baz/SKILL.md` then "
    "`~/.claude/skills/nw-distill/SKILL.md`.\n"
)


def _make_context(tmp_path):
    """Create an InstallContext with a minimal flat skill source layout."""
    project_root = tmp_path / "project"
    framework_source = tmp_path / "framework"

    skill_dir = project_root / "nWave" / "skills" / "nw-baz"
    skill_dir.mkdir(parents=True)
    source_file = skill_dir / "SKILL.md"
    source_file.write_text(_SKILL_WITH_SKILL_PATHS)

    (project_root / "nWave" / "framework-catalog.yaml").write_text("agents: {}\n")

    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)

    context = InstallContext(
        claude_dir=claude_dir,
        scripts_dir=tmp_path / "scripts",
        templates_dir=tmp_path / "templates",
        logger=MagicMock(),
        project_root=project_root,
        framework_source=framework_source,
        dev_mode=True,
    )

    opencode_skills_target = tmp_path / "home" / ".config" / "opencode" / "skills"
    return context, source_file, opencode_skills_target


class TestOpenCodeSkillBodyHasOpenCodeSkillPaths:
    """Skill installed for OpenCode must reference ~/.config/opencode/skills/."""

    def test_opencode_skill_body_has_opencode_skill_paths(self, tmp_path, monkeypatch):
        """
        GIVEN: A skill whose body references ~/.claude/skills/
        WHEN: The OpenCode skills plugin installs it
        THEN: ~/.config/opencode/skills/nw-baz/SKILL.md body contains
              ~/.config/opencode/skills/ AND NO ~/.claude/skills/.

        CONTRACT_SHAPE: bounded-change
        Outcome anchor: design.md value (DISCUSS wave skipped — optional)
        """
        context, _source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_skills_plugin._opencode_skills_dir",
            lambda: target,
        )

        result = OpenCodeSkillsPlugin().install(context)
        assert result.success is True

        installed = (target / "nw-baz" / "SKILL.md").read_text()
        assert "~/.config/opencode/skills/" in installed, (
            "Installed OpenCode skill body must use OpenCode skill paths"
        )
        assert "~/.claude/skills/" not in installed, (
            "Installed OpenCode skill body must NOT contain Claude Code skill paths"
        )

    def test_opencode_skill_source_byte_unchanged(self, tmp_path, monkeypatch):
        """
        GIVEN: A skill source with ~/.claude/skills/ paths
        WHEN: The OpenCode skills plugin installs it
        THEN: The SOURCE SKILL.md on disk is byte-unchanged AND the installed
              copy no longer references ~/.claude/skills/.

        CONTRACT_SHAPE: unbounded-preservation
        Outcome anchor: design.md value (DISCUSS wave skipped — optional)
        """
        context, source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_skills_plugin._opencode_skills_dir",
            lambda: target,
        )

        before = source.read_bytes()
        OpenCodeSkillsPlugin().install(context)

        assert source.read_bytes() == before, "Source skill file must NOT be mutated"
        installed = (target / "nw-baz" / "SKILL.md").read_text()
        assert "~/.claude/skills/" not in installed, (
            "Installed OpenCode skill body must NOT contain Claude Code skill paths"
        )

    def test_opencode_skill_installed_frontmatter_name_correct(
        self, tmp_path, monkeypatch
    ):
        """
        GIVEN: A skill source whose frontmatter name is nw-baz
        WHEN: The OpenCode skills plugin installs it
        THEN: The INSTALLED SKILL.md frontmatter name reflects the plugin's
              _rewrite_frontmatter_name transform -- for a non-colliding skill
              the resolved name equals the source name (nw-baz).

        NOTE: This is NOT active-RED. The frontmatter name transform already
        works today (design.md AC-3 sub-clause "name: transform still
        correct"). This test guards that existing invariant so the path-rewrite
        feature cannot silently break it -- observable installed-file assertion,
        not a direct _rewrite_frontmatter_name call.

        CONTRACT_SHAPE: bounded-change
        Outcome anchor: design.md value (DISCUSS wave skipped — optional)
        """
        context, _source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_skills_plugin._opencode_skills_dir",
            lambda: target,
        )

        OpenCodeSkillsPlugin().install(context)

        installed = (target / "nw-baz" / "SKILL.md").read_text()
        frontmatter, _body = parse_frontmatter(installed)
        assert frontmatter.get("name") == "nw-baz", (
            "Installed OpenCode skill frontmatter name must be correct"
        )
