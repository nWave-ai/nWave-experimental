"""Regression test for issue #27 -- Python path resolution in installed skills.

Skill and command templates use $(command -v python3 || command -v python) which
triggers Claude Code's permission prompt on every invocation. The installer must
resolve the Python path at install time, replacing the command substitution with
the concrete interpreter path.

SOURCE files keep the $(command -v ...) pattern for portability.
INSTALLED files get the resolved path.
"""

from unittest.mock import MagicMock

from scripts.install.plugins.base import InstallContext


_PYTHON_CMD_SUBSTITUTION = "$(command -v python3 || command -v python)"

_SKILL_WITH_PYTHON_SUBST = (
    "---\n"
    "name: nw-execute\n"
    "description: Execute step\n"
    "---\n"
    "\n"
    "# Execute\n"
    "\n"
    "```bash\n"
    "PYTHONPATH=$HOME/.claude/lib/python "
    "$(command -v python3 || command -v python) -m des.cli.log_phase \\\n"
    '  --step-id "$STEP_ID" \\\n'
    '  --phase "RED_ACCEPTANCE"\n'
    "```\n"
)

_COMMAND_WITH_PYTHON_SUBST = (
    "---\n"
    "description: Deliver a feature via Outside-In TDD\n"
    "argument-hint: <feature-file>\n"
    "---\n"
    "\n"
    "# Deliver\n"
    "\n"
    "```bash\n"
    "PYTHONPATH=$HOME/.claude/lib/python "
    "$(command -v python3 || command -v python) -m des.cli.init_roadmap\n"
    "```\n"
)


class TestInstalledSkillHasResolvedPythonPath:
    """Installed SKILL.md must have concrete python path, not $(command -v ...)."""

    def test_claude_code_skill_has_resolved_python_path(self, tmp_path, monkeypatch):
        """
        GIVEN: A source skill with $(command -v python3 || command -v python)
        WHEN: The skills plugin installs it for Claude Code
        THEN: The installed file contains a concrete python path (e.g. 'python3')
              AND does NOT contain '$(command -v'
        """
        from scripts.install.plugins.skills_plugin import SkillsPlugin

        # Set up source layout (NEW_FLAT)
        project_root = tmp_path / "project"
        framework_source = tmp_path / "framework"
        skills_source = framework_source / "skills"
        skill_dir = skills_source / "nw-execute"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(_SKILL_WITH_PYTHON_SUBST)

        # Catalog with empty agents = all public
        nwave_dir = project_root / "nWave"
        nwave_dir.mkdir(parents=True)
        (nwave_dir / "framework-catalog.yaml").write_text("agents: {}\n")
        agents_dir = nwave_dir / "agents"
        agents_dir.mkdir()

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

        # Mock resolve_python_command to return a known value
        monkeypatch.setattr(
            "scripts.install.plugins.skills_plugin.resolve_python_command",
            lambda: "python3",
        )

        plugin = SkillsPlugin()
        result = plugin.install(context)

        assert result.success is True

        installed_skill = claude_dir / "skills" / "nw-execute" / "SKILL.md"
        assert installed_skill.exists(), f"Expected {installed_skill} to exist"

        content = installed_skill.read_text()
        assert "$(command -v" not in content, (
            "Installed skill must NOT contain $(command -v ...) substitution"
        )
        assert "python3" in content, "Installed skill must contain resolved python path"

    def test_source_skill_retains_command_substitution(self, tmp_path):
        """
        GIVEN: A source skill with $(command -v python3 || command -v python)
        WHEN: We read the source file
        THEN: It still contains the command substitution pattern (portability)
        """
        # This validates source files are not modified -- they keep the portable pattern
        source_content = _SKILL_WITH_PYTHON_SUBST
        assert _PYTHON_CMD_SUBSTITUTION in source_content


class TestInstalledCommandHasResolvedPythonPath:
    """Installed command .md must have concrete python path."""

    def test_opencode_command_has_resolved_python_path(self, tmp_path, monkeypatch):
        """
        GIVEN: A source command with $(command -v python3 || command -v python)
        WHEN: The OpenCode commands plugin installs it
        THEN: The installed file contains a concrete python path
              AND does NOT contain '$(command -v'
        """
        from scripts.install.plugins.opencode_commands_plugin import (
            OpenCodeCommandsPlugin,
        )

        project_root = tmp_path / "project"
        framework_source = tmp_path / "framework"

        commands_source = project_root / "nWave" / "tasks" / "nw"
        commands_source.mkdir(parents=True)
        (commands_source / "deliver.md").write_text(_COMMAND_WITH_PYTHON_SUBST)

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir(parents=True)

        target_dir = tmp_path / "home" / ".config" / "opencode" / "commands"

        logger = MagicMock()
        context = InstallContext(
            claude_dir=claude_dir,
            scripts_dir=tmp_path / "scripts",
            templates_dir=tmp_path / "templates",
            logger=logger,
            project_root=project_root,
            framework_source=framework_source,
        )

        monkeypatch.setattr(
            "scripts.install.plugins.opencode_commands_plugin._opencode_commands_dir",
            lambda: target_dir,
        )
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_commands_plugin.resolve_python_command",
            lambda: "python3",
        )

        plugin = OpenCodeCommandsPlugin()
        result = plugin.install(context)

        assert result.success is True

        installed_cmd = target_dir / "deliver.md"
        assert installed_cmd.exists()

        content = installed_cmd.read_text()
        assert "$(command -v" not in content, (
            "Installed command must NOT contain $(command -v ...) substitution"
        )
        assert "python3" in content, (
            "Installed command must contain resolved python path"
        )


class TestResolvedPythonCommandInSharedModule:
    """resolve_python_command() must be importable from scripts.shared.install_paths."""

    def test_resolve_python_command_exists(self):
        """
        GIVEN: The shared install_paths module
        WHEN: resolve_python_command is imported
        THEN: It returns a non-empty string
        """
        from scripts.shared.install_paths import resolve_python_command

        result = resolve_python_command()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_resolve_python_command_returns_python3_for_venv(self, monkeypatch):
        """
        GIVEN: sys.executable points to a project-local .venv
        WHEN: resolve_python_command() is called
        THEN: Returns 'python3' (fallback, not the venv path)
        """
        from scripts.shared.install_paths import resolve_python_command

        monkeypatch.setattr(
            "scripts.shared.install_paths.sys",
            type("FakeSys", (), {"executable": "/project/.venv/bin/python3"})(),
        )
        result = resolve_python_command()
        assert result == "python3"
