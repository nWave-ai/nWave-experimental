"""
Unit tests for CommandsPlugin.

Tests the CommandsPlugin install() and verify() methods through the
InstallationPlugin interface (driving port).

Domain: Plugin Infrastructure - Commands Installation
"""

import logging
from pathlib import Path

import pytest

from scripts.install.plugins.base import InstallContext, PluginResult
from scripts.install.plugins.commands_plugin import CommandsPlugin


# -----------------------------------------------------------------------------
# Test Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def test_logger() -> logging.Logger:
    """Provide a configured logger for test execution."""
    logger = logging.getLogger("test.commands_plugin")
    logger.setLevel(logging.DEBUG)
    return logger


@pytest.fixture
def project_root() -> Path:
    """Return the nWave project root directory."""
    current = Path(__file__).resolve()
    return current.parents[4]  # 4 levels up from test file


@pytest.fixture
def commands_source_dir(project_root: Path) -> Path:
    """Return the commands source directory."""
    # Try dist/ide/commands first (built distribution)
    dist_path = project_root / "dist" / "ide" / "commands"
    if dist_path.exists():
        return dist_path

    # Fallback to nWave/commands
    source_path = project_root / "nWave" / "commands"
    if source_path.exists():
        return source_path

    # Final fallback
    return project_root / "nWave" / "commands"


@pytest.fixture
def install_context(tmp_path: Path, project_root: Path, test_logger: logging.Logger):
    """Create InstallContext for testing with real paths."""
    test_claude_dir = tmp_path / ".claude"
    test_claude_dir.mkdir(parents=True, exist_ok=True)

    return InstallContext(
        claude_dir=test_claude_dir,
        scripts_dir=project_root / "scripts" / "install",
        templates_dir=project_root / "nWave" / "templates",
        logger=test_logger,
        project_root=project_root,
        framework_source=project_root / "dist" / "ide",
        dry_run=False,
    )


# -----------------------------------------------------------------------------
# Priority and Name Tests
# -----------------------------------------------------------------------------


def test_commands_plugin_has_correct_name():
    """CommandsPlugin should have name 'commands'."""
    plugin = CommandsPlugin()
    assert plugin.name == "commands"


def test_commands_plugin_has_priority_20():
    """CommandsPlugin should have priority 20."""
    plugin = CommandsPlugin()
    assert plugin.priority == 20


def test_commands_plugin_has_no_dependencies():
    """CommandsPlugin should have no dependencies by default."""
    plugin = CommandsPlugin()
    assert plugin.get_dependencies() == []


# -----------------------------------------------------------------------------
# Install Tests
# -----------------------------------------------------------------------------


def test_commands_plugin_copies_files_to_target(
    install_context: InstallContext, commands_source_dir: Path
):
    """CommandsPlugin.install() should copy command files to target directory."""
    plugin = CommandsPlugin()
    target_commands_dir = install_context.claude_dir / "commands"

    # Act
    result = plugin.install(install_context)

    # Assert - depends on whether source exists
    if commands_source_dir.exists():
        assert result.success, f"Installation failed: {result.message}"
        assert target_commands_dir.exists(), (
            f"Target directory not created: {target_commands_dir}"
        )
    else:
        # Source doesn't exist, should fail gracefully
        assert not result.success


def test_commands_plugin_install_returns_plugin_result(install_context: InstallContext):
    """CommandsPlugin.install() should return PluginResult."""
    plugin = CommandsPlugin()

    result = plugin.install(install_context)

    assert isinstance(result, PluginResult)
    assert result.plugin_name == "commands"


def test_commands_plugin_install_handles_missing_source_gracefully(
    tmp_path: Path, test_logger: logging.Logger
):
    """CommandsPlugin.install() should handle missing source directory."""
    # Arrange - context with non-existent framework_source
    test_claude_dir = tmp_path / ".claude"
    test_claude_dir.mkdir(parents=True, exist_ok=True)

    context = InstallContext(
        claude_dir=test_claude_dir,
        scripts_dir=tmp_path / "scripts",
        templates_dir=tmp_path / "templates",
        logger=test_logger,
        project_root=tmp_path,
        framework_source=tmp_path / "non_existent",
        dry_run=False,
    )

    plugin = CommandsPlugin()

    # Act
    result = plugin.install(context)

    # Assert - should fail gracefully, not crash
    assert not result.success
    assert "does not exist" in result.message


# -----------------------------------------------------------------------------
# Verify Tests
# -----------------------------------------------------------------------------


def test_commands_plugin_verify_confirms_files_exist(install_context: InstallContext):
    """CommandsPlugin.verify() should confirm command files were installed."""
    plugin = CommandsPlugin()

    # Install first
    install_result = plugin.install(install_context)

    if install_result.success:
        # Verify
        verify_result = plugin.verify(install_context)

        # Check verification result
        assert verify_result.success is True
        assert "Commands verification passed" in verify_result.message


def test_commands_plugin_verify_fails_when_target_directory_missing(
    tmp_path: Path, project_root: Path, test_logger: logging.Logger
):
    """CommandsPlugin.verify() should fail when target directory does not exist."""
    # Arrange - create context with empty claude_dir (no install)
    empty_claude_dir = tmp_path / ".claude-empty"
    empty_claude_dir.mkdir(parents=True, exist_ok=True)

    context = InstallContext(
        claude_dir=empty_claude_dir,
        scripts_dir=project_root / "scripts" / "install",
        templates_dir=project_root / "nWave" / "templates",
        logger=test_logger,
        project_root=project_root,
        framework_source=project_root / "dist" / "ide",
        dry_run=False,
    )

    plugin = CommandsPlugin()

    # Act - verify without install
    verify_result = plugin.verify(context)

    # Assert - should fail because no installation occurred
    assert verify_result.success is False
    assert "target directory does not exist" in verify_result.message


def test_commands_plugin_verify_fails_when_no_command_files(
    tmp_path: Path, project_root: Path, test_logger: logging.Logger
):
    """CommandsPlugin.verify() should fail when directory exists but has no .md files."""
    # Arrange - create context with commands/nw directory but no files
    claude_dir = tmp_path / ".claude-nofiles"
    commands_dir = claude_dir / "commands" / "nw"
    commands_dir.mkdir(parents=True, exist_ok=True)

    context = InstallContext(
        claude_dir=claude_dir,
        scripts_dir=project_root / "scripts" / "install",
        templates_dir=project_root / "nWave" / "templates",
        logger=test_logger,
        project_root=project_root,
        framework_source=project_root / "dist" / "ide",
        dry_run=False,
    )

    plugin = CommandsPlugin()

    # Act - verify with empty directory
    verify_result = plugin.verify(context)

    # Assert - should fail because no command files
    assert verify_result.success is False
    assert "no command files found" in verify_result.message
