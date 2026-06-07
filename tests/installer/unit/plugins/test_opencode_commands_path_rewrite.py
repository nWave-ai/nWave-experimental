"""Tests for OpenCode commands plugin path rewriting.

Validates that the commands plugin rewrites Claude Code paths to OpenCode
equivalents during install(), using rules from platform_contracts.py (SSOT).

Walking Skeleton WS-2: install() produces command files with rewritten paths.
ANOMALY-1: DES library paths must NOT be rewritten.

CRITICAL: Acceptance tests exercise install() driving port end-to-end.
Litmus test: "If I delete _rewrite_paths() call, does this test fail?" -> YES.
"""

from unittest.mock import MagicMock

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.opencode_commands_plugin import (
    OpenCodeCommandsPlugin,
)


def _make_context(tmp_path):
    """Create an InstallContext with a minimal command source layout."""
    project_root = tmp_path / "project"
    framework_source = tmp_path / "framework"

    commands_source = project_root / "nWave" / "tasks" / "nw"
    commands_source.mkdir(parents=True)

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

    opencode_commands_target = tmp_path / "home" / ".config" / "opencode" / "commands"

    return context, commands_source, opencode_commands_target


def _create_command(commands_source, command_name, content):
    """Create a command .md file in the source layout."""
    (commands_source / f"{command_name}.md").write_text(content)


# -- Walking Skeleton WS-2: install() rewrites skill paths -------------------


_COMMAND_WITH_SKILL_PATH = (
    "---\n"
    'description: "Delivers working code via TDD."\n'
    "---\n"
    "\n"
    "# NW-DELIVER\n"
    "\n"
    "Load skill: ~/.claude/skills/nw-tdd/SKILL.md\n"
)

_COMMAND_WITH_AGENT_PATH = (
    "---\n"
    'description: "Research command."\n'
    "---\n"
    "\n"
    "# NW-RESEARCH\n"
    "\n"
    "Delegate to ~/.claude/agents/nw/nw-researcher.md for research tasks.\n"
)

_COMMAND_WITH_FRAMEWORK_PATH = (
    "---\n"
    'description: "Uses common skills."\n'
    "---\n"
    "\n"
    "# NW-COMMON\n"
    "\n"
    "Load from ~/.claude/nWave/skills/common/shared-skill.md\n"
)

_COMMAND_WITH_DES_LIB_PATH = (
    "---\n"
    'description: "Uses DES runtime."\n'
    "---\n"
    "\n"
    "# NW-DES\n"
    "\n"
    "PYTHONPATH=~/.claude/lib/python python3 -m des.cli.log_phase\n"
    "Also load: ~/.claude/skills/nw-tdd/SKILL.md\n"
)


class TestInstallRewritesSkillPaths:
    """WS-2: install() produces command files with skill paths rewritten."""

    def test_install_rewrites_skill_path_to_opencode(self, tmp_path, monkeypatch):
        """
        GIVEN: A command file referencing ~/.claude/skills/nw-tdd/SKILL.md
        WHEN: install() is called
        THEN: Output file contains ~/.config/opencode/skills/nw-tdd/SKILL.md
        """
        context, commands_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_commands_plugin._opencode_commands_dir",
            lambda: target,
        )

        _create_command(commands_source, "deliver", _COMMAND_WITH_SKILL_PATH)

        plugin = OpenCodeCommandsPlugin()
        result = plugin.install(context)

        assert result.success is True

        content = (target / "deliver.md").read_text()
        assert "~/.config/opencode/skills/nw-tdd/SKILL.md" in content
        assert "~/.claude/skills/" not in content


class TestInstallRewritesAgentPaths:
    """install() rewrites agent paths from Claude Code to OpenCode."""

    def test_install_rewrites_agent_path_to_opencode(self, tmp_path, monkeypatch):
        """
        GIVEN: A command file referencing ~/.claude/agents/nw/nw-researcher.md
        WHEN: install() is called
        THEN: Output file contains ~/.config/opencode/agents/nw/nw-researcher.md
        """
        context, commands_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_commands_plugin._opencode_commands_dir",
            lambda: target,
        )

        _create_command(commands_source, "research", _COMMAND_WITH_AGENT_PATH)

        plugin = OpenCodeCommandsPlugin()
        result = plugin.install(context)

        assert result.success is True

        content = (target / "research.md").read_text()
        assert "~/.config/opencode/agents/nw/nw-researcher.md" in content
        assert "~/.claude/agents/" not in content


class TestInstallRewritesFrameworkPaths:
    """install() rewrites nWave framework paths."""

    def test_install_rewrites_framework_skill_path(self, tmp_path, monkeypatch):
        """
        GIVEN: A command file referencing ~/.claude/nWave/skills/common/
        WHEN: install() is called
        THEN: Output file contains ~/.config/opencode/skills/common/
        """
        context, commands_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_commands_plugin._opencode_commands_dir",
            lambda: target,
        )

        _create_command(commands_source, "common", _COMMAND_WITH_FRAMEWORK_PATH)

        plugin = OpenCodeCommandsPlugin()
        result = plugin.install(context)

        assert result.success is True

        content = (target / "common.md").read_text()
        assert "~/.config/opencode/skills/common/shared-skill.md" in content
        assert "~/.claude/nWave/" not in content


class TestInstallPreservesDESLibraryPath:
    """ANOMALY-1: DES library path ~/.claude/lib/python must NOT be rewritten."""

    def test_install_does_not_rewrite_des_lib_path(self, tmp_path, monkeypatch):
        """
        GIVEN: A command file with both DES lib path and skill path
        WHEN: install() is called
        THEN: DES lib path remains ~/.claude/lib/python (not rewritten)
              AND skill path IS rewritten to ~/.config/opencode/
        """
        context, commands_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_commands_plugin._opencode_commands_dir",
            lambda: target,
        )

        _create_command(commands_source, "des", _COMMAND_WITH_DES_LIB_PATH)

        plugin = OpenCodeCommandsPlugin()
        result = plugin.install(context)

        assert result.success is True

        content = (target / "des.md").read_text()
        # DES lib path must NOT be rewritten
        assert "~/.claude/lib/python" in content
        # Skill path MUST be rewritten
        assert "~/.config/opencode/skills/nw-tdd/SKILL.md" in content
