"""Unit tests for OpenCode commands installer plugin.

Tests validate that:
- _transform_frontmatter() removes argument-hint and disable-model-invocation
- _transform_frontmatter() keeps description unchanged
- _transform_command() produces a complete OpenCode-format command file
- install() creates transformed command files in the target directory
- install() preserves body content unchanged
- uninstall() only removes manifest-tracked commands, not user-created ones
- install() creates a .nwave-commands-manifest.json tracking installed commands

CRITICAL: Tests follow hexagonal architecture - mocks only at port boundaries.
"""

import json
from unittest.mock import MagicMock

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.opencode_commands_plugin import (
    OpenCodeCommandsPlugin,
    _transform_command,
    _transform_frontmatter,
)
from scripts.install.plugins.opencode_common import parse_frontmatter


def _make_context(tmp_path):
    """Create an InstallContext with a minimal command source layout.

    Returns:
        Tuple of (context, commands_source, opencode_commands_target)
    """
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
    """Create a command .md file in the source layout.

    Args:
        commands_source: Path to nWave/tasks/nw/ directory
        command_name: Command filename without extension (e.g. 'deliver')
        content: Full file content with frontmatter + body
    """
    (commands_source / f"{command_name}.md").write_text(content)


_COMMAND_WITH_ARGUMENT_HINT = (
    "---\n"
    'description: "Designs system architecture with C4 diagrams."\n'
    'argument-hint: "[component-name] - Optional: --paradigm=[auto|oop|fp]"\n'
    "---\n"
    "\n"
    "# NW-DESIGN: Architecture Design\n"
    "\n"
    "Body content here.\n"
)

_COMMAND_WITH_DISABLE_MODEL = (
    "---\n"
    'description: "Archives a completed feature to docs/evolution/."\n'
    "disable-model-invocation: true\n"
    "argument-hint: '[agent] [feature-id] - Example: @platform-architect \"auth\"'\n"
    "---\n"
    "\n"
    "# NW-FINALIZE: Feature Completion\n"
    "\n"
    "Finalize body content.\n"
)

_COMMAND_DESCRIPTION_ONLY = (
    "---\n"
    'description: "Simple command with only description."\n'
    "---\n"
    "\n"
    "# NW-SIMPLE: Simple Command\n"
    "\n"
    "Simple body.\n"
)


class TestTransformRemovesArgumentHint:
    """Test that _transform_frontmatter removes argument-hint field."""

    def test_transform_removes_argument_hint(self):
        """
        GIVEN: A frontmatter dict with argument-hint field
        WHEN: _transform_frontmatter() is called
        THEN: argument-hint is not in the result
        """
        frontmatter = {
            "description": "Designs system architecture.",
            "argument-hint": "[component-name] - Optional: --paradigm=[auto|oop|fp]",
        }

        result = _transform_frontmatter(frontmatter)

        assert "argument-hint" not in result


class TestTransformRemovesDisableModelInvocation:
    """Test that _transform_frontmatter removes disable-model-invocation field."""

    def test_transform_removes_disable_model_invocation(self):
        """
        GIVEN: A frontmatter dict with disable-model-invocation field
        WHEN: _transform_frontmatter() is called
        THEN: disable-model-invocation is not in the result
        """
        frontmatter = {
            "description": "Archives a completed feature.",
            "disable-model-invocation": True,
            "argument-hint": "[agent] [feature-id]",
        }

        result = _transform_frontmatter(frontmatter)

        assert "disable-model-invocation" not in result


class TestTransformKeepsDescription:
    """Test that _transform_frontmatter preserves description exactly."""

    def test_transform_keeps_description(self):
        """
        GIVEN: A frontmatter dict with description field
        WHEN: _transform_frontmatter() is called
        THEN: description is preserved with the exact same value
        """
        frontmatter = {
            "description": "Designs system architecture with C4 diagrams.",
            "argument-hint": "[component-name]",
            "disable-model-invocation": True,
        }

        result = _transform_frontmatter(frontmatter)

        assert result["description"] == "Designs system architecture with C4 diagrams."


class TestInstallCreatesCommandFiles:
    """Test that install() creates transformed command files in the target directory."""

    def test_install_creates_command_files(self, tmp_path, monkeypatch):
        """
        GIVEN: A source command at nWave/tasks/nw/design.md
        WHEN: install() is called
        THEN: design.md is created in the OpenCode commands directory
              with transformed frontmatter (no argument-hint)
        """
        context, commands_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_commands_plugin._opencode_commands_dir",
            lambda: target,
        )

        _create_command(commands_source, "design", _COMMAND_WITH_ARGUMENT_HINT)

        plugin = OpenCodeCommandsPlugin()
        result = plugin.install(context)

        assert result.success is True

        command_file = target / "design.md"
        assert command_file.exists(), f"Expected {command_file} to exist"

        content = command_file.read_text()
        assert "argument-hint" not in content
        assert "description:" in content


class TestInstallPreservesBody:
    """Test that install() preserves body content unchanged after transformation."""

    def test_install_preserves_body(self, tmp_path, monkeypatch):
        """
        GIVEN: A command file with specific body content
        WHEN: install() transforms it
        THEN: The body content after the frontmatter is unchanged
        """
        context, commands_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_commands_plugin._opencode_commands_dir",
            lambda: target,
        )

        _create_command(commands_source, "design", _COMMAND_WITH_ARGUMENT_HINT)

        plugin = OpenCodeCommandsPlugin()
        plugin.install(context)

        command_file = target / "design.md"
        content = command_file.read_text()

        # Parse source to get original body
        _, source_body = parse_frontmatter(_COMMAND_WITH_ARGUMENT_HINT)

        # Parse output to get transformed body
        _, output_body = parse_frontmatter(content)

        assert output_body == source_body


class TestUninstallRemovesOnlyManifestCommands:
    """Test that uninstall() removes only manifest-tracked commands."""

    def test_uninstall_removes_only_manifest_commands(self, tmp_path, monkeypatch):
        """
        GIVEN: An OpenCode commands directory with both nWave-installed and
               user-created command files
        WHEN: uninstall() is called
        THEN: Only nWave-installed commands (listed in manifest) are removed;
              user-created commands remain untouched
        """
        context, _commands_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_commands_plugin._opencode_commands_dir",
            lambda: target,
        )

        target.mkdir(parents=True, exist_ok=True)

        # Create nWave-installed command
        nwave_command = target / "design.md"
        nwave_command.write_text("---\ndescription: Architecture\n---\n\n# Design\n")

        # Create user-owned command (NOT in manifest)
        user_command = target / "my-custom-command.md"
        user_command.write_text("---\ndescription: My cmd\n---\n\n# My cmd\n")

        # Manifest only tracks nWave commands
        manifest = {
            "installed_commands": ["design"],
            "version": "1.0",
        }
        (target / ".nwave-commands-manifest.json").write_text(json.dumps(manifest))

        plugin = OpenCodeCommandsPlugin()
        result = plugin.uninstall(context)

        assert result.success is True

        # nWave command should be removed
        assert not nwave_command.exists(), "nWave command should be removed"

        # User command should remain
        assert user_command.exists(), "User-created command must remain untouched"


class TestInstallCreatesManifest:
    """Test that install() creates a manifest tracking installed command names."""

    def test_install_creates_manifest(self, tmp_path, monkeypatch):
        """
        GIVEN: Multiple source command files
        WHEN: install() is called
        THEN: A .nwave-commands-manifest.json is created listing all installed commands
        """
        context, commands_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_commands_plugin._opencode_commands_dir",
            lambda: target,
        )

        _create_command(commands_source, "design", _COMMAND_WITH_ARGUMENT_HINT)
        _create_command(commands_source, "finalize", _COMMAND_WITH_DISABLE_MODEL)

        plugin = OpenCodeCommandsPlugin()
        plugin.install(context)

        manifest_path = target / ".nwave-commands-manifest.json"
        assert manifest_path.exists(), "Manifest should be created"

        manifest = json.loads(manifest_path.read_text())
        assert "installed_commands" in manifest
        assert sorted(manifest["installed_commands"]) == sorted(["design", "finalize"])


class TestTransformCommandFullPipeline:
    """Test the full _transform_command pipeline from source to OpenCode format."""

    def test_transform_command_with_all_removals(self):
        """
        GIVEN: A command file with argument-hint and disable-model-invocation
        WHEN: _transform_command() is called
        THEN: Produces valid OpenCode format with both fields removed
              and description + body preserved
        """
        result = _transform_command(_COMMAND_WITH_DISABLE_MODEL)

        frontmatter, body = parse_frontmatter(result)

        assert (
            frontmatter["description"]
            == "Archives a completed feature to docs/evolution/."
        )
        assert "argument-hint" not in frontmatter
        assert "disable-model-invocation" not in frontmatter

        assert "# NW-FINALIZE: Feature Completion" in body
        assert "Finalize body content." in body

    def test_transform_command_description_only(self):
        """
        GIVEN: A command file with only description (no fields to remove)
        WHEN: _transform_command() is called
        THEN: Produces identical output (description preserved, body unchanged)
        """
        result = _transform_command(_COMMAND_DESCRIPTION_ONLY)

        frontmatter, body = parse_frontmatter(result)

        assert frontmatter["description"] == "Simple command with only description."
        assert len(frontmatter) == 1  # only description remains

        assert "# NW-SIMPLE: Simple Command" in body
        assert "Simple body." in body
