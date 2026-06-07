"""
Unit tests for CommandsPlugin (legacy cleanup).

Since v2.8.0, commands are installed as skills by SkillsPlugin.
CommandsPlugin now only removes the legacy commands/nw/ directory.

Domain: Plugin Infrastructure - Legacy Commands Cleanup
"""

import logging
from pathlib import Path

import pytest

from scripts.install.plugins.base import InstallContext
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
def install_context(tmp_path: Path, project_root: Path, test_logger: logging.Logger):
    """Create InstallContext for testing."""
    test_claude_dir = tmp_path / ".claude"
    test_claude_dir.mkdir(parents=True, exist_ok=True)

    return InstallContext(
        claude_dir=test_claude_dir,
        scripts_dir=project_root / "scripts" / "install",
        templates_dir=project_root / "nWave" / "templates",
        logger=test_logger,
        project_root=project_root,
        framework_source=tmp_path / "nonexistent_dist",
        dry_run=False,
    )


# -----------------------------------------------------------------------------
# Cleanup behavior tests
# -----------------------------------------------------------------------------


def test_commands_plugin_removes_legacy_commands_dir(
    install_context: InstallContext,
):
    """CommandsPlugin removes commands/nw/ if it exists from a prior install."""
    legacy_dir = install_context.claude_dir / "commands" / "nw"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "deliver.md").write_text("# old command")
    (legacy_dir / "design.md").write_text("# old command")

    plugin = CommandsPlugin()
    result = plugin.install(install_context)

    assert result.success
    assert not legacy_dir.exists()
    assert "2 files" in result.message


def test_commands_plugin_succeeds_when_no_legacy_dir(
    install_context: InstallContext,
):
    """CommandsPlugin succeeds even if commands/nw/ doesn't exist."""
    plugin = CommandsPlugin()
    result = plugin.install(install_context)

    assert result.success
    assert "No legacy commands" in result.message


class TestCommandsPluginVerify:
    """Verify checks that legacy directory is gone."""

    def test_verify_passes_when_no_legacy_dir(self, install_context: InstallContext):
        """Verify passes when commands/nw/ does not exist."""
        plugin = CommandsPlugin()
        result = plugin.verify(install_context)

        assert result.success
        assert "migrated to skills" in result.message

    def test_verify_fails_when_legacy_dir_still_exists(
        self, install_context: InstallContext
    ):
        """Verify fails if commands/nw/ still exists after cleanup."""
        legacy_dir = install_context.claude_dir / "commands" / "nw"
        legacy_dir.mkdir(parents=True)

        plugin = CommandsPlugin()
        result = plugin.verify(install_context)

        assert result.success is False
        assert "still exists" in result.message
