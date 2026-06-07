"""Regression test for issue #27 -- OpenCode agent skill path rewriting.

Agent bodies contain hardcoded ~/.claude/skills/ paths which break on OpenCode
where skills live at ~/.config/opencode/skills/. The OpenCode agents plugin must
rewrite these paths during installation.
"""

from unittest.mock import MagicMock

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.opencode_agents_plugin import (
    OpenCodeAgentsPlugin,
)
from scripts.install.plugins.opencode_common import parse_frontmatter


_AGENT_WITH_SKILL_PATHS = (
    "---\n"
    "name: nw-software-crafter\n"
    "description: DELIVER wave - Outside-In TDD\n"
    "model: inherit\n"
    "tools: Read, Write, Edit, Bash\n"
    "maxTurns: 50\n"
    "---\n"
    "\n"
    "# nw-software-crafter\n"
    "\n"
    "## Skill Loading -- MANDATORY\n"
    "\n"
    "Read these files NOW:\n"
    "- `~/.claude/skills/nw-tdd-methodology/SKILL.md`\n"
    "- `~/.claude/skills/nw-quality-framework/SKILL.md`\n"
    "\n"
    "### On-Demand\n"
    "\n"
    "| Skill | Trigger |\n"
    "| `~/.claude/skills/nw-hexagonal-testing/SKILL.md` | Port decisions |\n"
    "| `~/.claude/skills/nw-property-based-testing/SKILL.md` | @property |\n"
)


def _make_context(tmp_path):
    """Create an InstallContext with a minimal agent source layout."""
    project_root = tmp_path / "project"
    framework_source = tmp_path / "framework"

    agents_source = project_root / "nWave" / "agents"
    agents_source.mkdir(parents=True)

    (project_root / "nWave" / "framework-catalog.yaml").write_text(
        "agents: {}\n",
    )

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

    opencode_agents_target = tmp_path / "home" / ".config" / "opencode" / "agents"

    return context, agents_source, opencode_agents_target


class TestOpenCodeAgentBodyHasOpenCodeSkillPaths:
    """Agent installed for OpenCode must reference ~/.config/opencode/skills/."""

    def test_opencode_agent_body_has_opencode_skill_paths(self, tmp_path, monkeypatch):
        """
        GIVEN: A source agent with ~/.claude/skills/ paths in the body
        WHEN: The OpenCode agents plugin installs it
        THEN: The installed file contains ~/.config/opencode/skills/
              AND does NOT contain ~/.claude/skills/
        """
        context, agents_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_agents_plugin._opencode_agents_dir",
            lambda: target,
        )

        (agents_source / "nw-software-crafter.md").write_text(_AGENT_WITH_SKILL_PATHS)

        plugin = OpenCodeAgentsPlugin()
        result = plugin.install(context)

        assert result.success is True

        installed_content = (target / "nw-software-crafter.md").read_text()
        _, body = parse_frontmatter(installed_content)

        assert "~/.config/opencode/skills/" in body, (
            "Installed agent body must use OpenCode skill paths"
        )
        assert "~/.claude/skills/" not in body, (
            "Installed agent body must NOT contain Claude Code skill paths"
        )

    def test_source_agent_retains_claude_code_paths(self, tmp_path, monkeypatch):
        """
        GIVEN: A source agent with ~/.claude/skills/ paths
        WHEN: The OpenCode agents plugin installs it
        THEN: The SOURCE file is NOT modified (only the installed copy changes)
        """
        context, agents_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_agents_plugin._opencode_agents_dir",
            lambda: target,
        )

        source_file = agents_source / "nw-software-crafter.md"
        source_file.write_text(_AGENT_WITH_SKILL_PATHS)

        plugin = OpenCodeAgentsPlugin()
        plugin.install(context)

        source_content = source_file.read_text()
        assert "~/.claude/skills/" in source_content, (
            "Source file must retain original Claude Code paths"
        )
