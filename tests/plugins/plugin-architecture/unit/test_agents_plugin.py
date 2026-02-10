"""
Unit tests for AgentsPlugin.

Tests the AgentsPlugin install() and verify() methods through the
InstallationPlugin interface (driving port).

Domain: Plugin Infrastructure - Agent Installation
"""

import logging
from pathlib import Path

import pytest

from scripts.install.plugins.agents_plugin import AgentsPlugin
from scripts.install.plugins.base import InstallContext, PluginResult


# -----------------------------------------------------------------------------
# Test Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def test_logger() -> logging.Logger:
    """Provide a configured logger for test execution."""
    logger = logging.getLogger("test.agents_plugin")
    logger.setLevel(logging.DEBUG)
    return logger


@pytest.fixture
def project_root() -> Path:
    """Return the nWave project root directory."""
    current = Path(__file__).resolve()
    return current.parents[4]  # 4 levels up from test file


@pytest.fixture
def agent_source_dir(project_root: Path) -> Path:
    """Return the agent source directory."""
    # Try dist/ide/agents/nw first (built distribution)
    dist_path = project_root / "dist" / "ide" / "agents" / "nw"
    if dist_path.exists():
        return dist_path

    # Fallback to nWave/agents/nw (source)
    source_path = project_root / "nWave" / "agents" / "nw"
    if source_path.exists():
        return source_path

    # Final fallback to nWave/agents
    return project_root / "nWave" / "agents"


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
# Test Class: AgentsPluginShould
# -----------------------------------------------------------------------------


class AgentsPluginShould:
    """Unit tests for AgentsPlugin following naming convention."""

    def test_copy_agent_files_to_target_directory_when_install_called(
        self, install_context: InstallContext, agent_source_dir: Path
    ):
        """
        AgentsPlugin.install() should copy agent .md files to the target directory.

        Given: A valid InstallContext with project root containing agent source files
        When: install() is called
        Then: Agent files are copied to {claude_dir}/agents/nw/
        """
        # Arrange
        plugin = AgentsPlugin()
        target_agents_dir = install_context.claude_dir / "agents" / "nw"

        # Verify source files exist
        assert agent_source_dir.exists(), f"Agent source not found: {agent_source_dir}"
        source_files = list(agent_source_dir.glob("*.md"))
        assert len(source_files) >= 1, "No agent .md files in source directory"

        # Act
        result = plugin.install(install_context)

        # Assert
        assert result.success, f"Installation failed: {result.message}"
        assert target_agents_dir.exists(), (
            f"Target directory not created: {target_agents_dir}"
        )

        target_files = list(target_agents_dir.glob("*.md"))
        assert len(target_files) >= 1, (
            f"Expected at least 1 agent file in target, found {len(target_files)}"
        )

    def test_return_success_result_with_installed_files_list_when_install_succeeds(
        self, install_context: InstallContext
    ):
        """
        AgentsPlugin.install() should return PluginResult with installed_files populated.

        Given: A valid InstallContext
        When: install() is called successfully
        Then: PluginResult.success is True and installed_files contains file paths
        """
        # Arrange
        plugin = AgentsPlugin()

        # Act
        result = plugin.install(install_context)

        # Assert
        assert isinstance(result, PluginResult)
        assert result.success is True
        assert result.plugin_name == "agents"
        assert (
            "Agents installed" in result.message or "success" in result.message.lower()
        )
        # installed_files should contain the copied files
        assert result.installed_files is not None

    def test_return_success_with_verification_message_when_verify_called_after_install(
        self, install_context: InstallContext
    ):
        """
        AgentsPlugin.verify() should confirm installation was successful.

        Given: AgentsPlugin.install() was called successfully
        When: verify() is called
        Then: PluginResult.success is True and message contains 'Agents verification passed'
        """
        # Arrange
        plugin = AgentsPlugin()

        # First install
        install_result = plugin.install(install_context)
        assert install_result.success, f"Install failed: {install_result.message}"

        # Act
        verify_result = plugin.verify(install_context)

        # Assert
        assert verify_result.success is True
        assert "Agents verification passed" in verify_result.message

    def test_verify_checks_target_directory_contains_agent_files(
        self, install_context: InstallContext
    ):
        """
        AgentsPlugin.verify() should check that agent files exist in target directory.

        Given: Installation completed
        When: verify() is called
        Then: Verification checks for presence of agent files
        """
        # Arrange
        plugin = AgentsPlugin()

        # Install first
        plugin.install(install_context)

        # Act
        verify_result = plugin.verify(install_context)

        # Assert
        assert verify_result.success is True
        # The verification should have actually checked for files
        target_dir = install_context.claude_dir / "agents" / "nw"
        if target_dir.exists():
            agent_files = list(target_dir.glob("*.md"))
            # If files exist, verification should pass
            # If files don't exist, this test reveals the stub doesn't really verify
            assert len(agent_files) >= 1 or not verify_result.success


# -----------------------------------------------------------------------------
# Standalone Test Functions (for pytest discovery)
# -----------------------------------------------------------------------------


def test_agents_plugin_copies_files_to_target(
    install_context: InstallContext, agent_source_dir: Path
):
    """AgentsPlugin.install() should copy agent files to target directory."""
    plugin = AgentsPlugin()
    target_agents_dir = install_context.claude_dir / "agents" / "nw"

    # Verify source exists
    assert agent_source_dir.exists(), f"Agent source not found: {agent_source_dir}"

    # Act
    result = plugin.install(install_context)

    # Assert - this should fail with current stub implementation
    assert result.success, f"Installation failed: {result.message}"
    assert target_agents_dir.exists(), (
        f"Target directory not created: {target_agents_dir}"
    )

    target_files = list(target_agents_dir.glob("*.md"))
    assert len(target_files) >= 1, (
        f"Expected at least 1 agent file in target, found {len(target_files)}"
    )


def test_agents_plugin_verify_confirms_files_exist(install_context: InstallContext):
    """AgentsPlugin.verify() should confirm agent files were installed."""
    plugin = AgentsPlugin()

    # Install first
    install_result = plugin.install(install_context)
    assert install_result.success

    # Verify
    verify_result = plugin.verify(install_context)

    # Check verification result
    assert verify_result.success is True
    assert "Agents verification passed" in verify_result.message


def test_agents_plugin_verify_fails_when_target_directory_missing(
    tmp_path: Path, project_root: Path, test_logger: logging.Logger
):
    """AgentsPlugin.verify() should fail when target directory does not exist."""
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

    plugin = AgentsPlugin()

    # Act - verify without install
    verify_result = plugin.verify(context)

    # Assert - should fail because no installation occurred
    assert verify_result.success is False
    assert "target directory does not exist" in verify_result.message


def test_agents_plugin_verify_fails_when_no_agent_files(
    tmp_path: Path, project_root: Path, test_logger: logging.Logger
):
    """AgentsPlugin.verify() should fail when directory exists but has no .md files."""
    # Arrange - create context with agents/nw directory but no files
    claude_dir = tmp_path / ".claude-nofiles"
    agents_dir = claude_dir / "agents" / "nw"
    agents_dir.mkdir(parents=True, exist_ok=True)

    context = InstallContext(
        claude_dir=claude_dir,
        scripts_dir=project_root / "scripts" / "install",
        templates_dir=project_root / "nWave" / "templates",
        logger=test_logger,
        project_root=project_root,
        framework_source=project_root / "dist" / "ide",
        dry_run=False,
    )

    plugin = AgentsPlugin()

    # Act - verify with empty directory
    verify_result = plugin.verify(context)

    # Assert - should fail because no agent files
    assert verify_result.success is False
    assert "no agent files found" in verify_result.message
