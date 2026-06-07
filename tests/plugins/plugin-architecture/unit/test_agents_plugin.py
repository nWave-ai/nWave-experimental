"""
Unit tests for AgentsPlugin.

Tests the AgentsPlugin install() and verify() methods through the
InstallationPlugin interface (driving port).

Source: nWave/agents/ (no dist/ide fallback)
Excludes: README.md

Domain: Plugin Infrastructure - Agent Installation
"""

import logging
from pathlib import Path

import pytest

from scripts.install.plugins.agents_plugin import AgentsPlugin
from scripts.install.plugins.base import InstallContext, PluginResult
from scripts.shared.agent_catalog import is_public_agent, load_public_agents


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
    """Return the canonical agent source directory: nWave/agents/."""
    return project_root / "nWave" / "agents"


@pytest.fixture
def public_agents(project_root: Path) -> set[str]:
    """Return the set of public agent names from framework-catalog.yaml."""
    return load_public_agents(project_root / "nWave")


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
        framework_source=project_root / "nWave",
        dry_run=False,
    )


# -----------------------------------------------------------------------------
# Acceptance Test: Single source, no dist/ide, installs only nw-*.md agents
# -----------------------------------------------------------------------------


def test_agents_plugin_installs_only_public_nw_agents(
    install_context: InstallContext,
    public_agents: set[str],
):
    """AgentsPlugin.install() should install only public nw-*.md files from nWave/agents/.

    Acceptance test: After install, the target directory must contain only
    public nw-*.md files from nWave/agents/ root. No config.json (dist/ide
    artifact) and no README.md should be present. Private agents (marked
    public: false in framework-catalog.yaml) must be excluded.
    """
    # Arrange
    plugin = AgentsPlugin()
    target_agents_dir = install_context.claude_dir / "agents" / "nw"
    source_agents_dir = install_context.project_root / "nWave" / "agents"

    # Count expected: only public nw-*.md files in nWave/agents/ root
    expected_public_files = [
        f
        for f in source_agents_dir.glob("nw-*.md")
        if is_public_agent(f.name, public_agents)
    ]
    assert len(expected_public_files) >= 20, (
        f"Expected at least 20 public nw-*.md agent files in source, "
        f"found {len(expected_public_files)}"
    )

    # Act
    result = plugin.install(install_context)

    # Assert - installation succeeded
    assert result.success, f"Installation failed: {result.message}"

    # Assert - no config.json (dist/ide artifact) was copied
    config_json = target_agents_dir / "config.json"
    assert not config_json.exists(), (
        "config.json (dist/ide artifact) should not be present in target"
    )

    # Assert - target contains only public nw-*.md files
    target_files = list(target_agents_dir.glob("nw-*.md"))
    assert len(target_files) == len(expected_public_files), (
        f"Expected {len(expected_public_files)} public nw-*.md files in target, "
        f"found {len(target_files)}"
    )


# -----------------------------------------------------------------------------
# Unit Tests: AgentsPluginShould
# -----------------------------------------------------------------------------


class TestAgentsPluginShould:
    """Unit tests for AgentsPlugin through the InstallationPlugin interface."""

    def test_copy_public_nw_agent_files_from_nwave_agents_to_target(
        self,
        install_context: InstallContext,
        agent_source_dir: Path,
        public_agents: set[str],
    ):
        """
        Given: nWave/agents/ contains nw-*.md agent files (public and private)
        When: install() is called
        Then: Only public nw-*.md files are copied to {claude_dir}/agents/nw/
        """
        plugin = AgentsPlugin()
        target_agents_dir = install_context.claude_dir / "agents" / "nw"

        assert agent_source_dir.exists(), f"Agent source not found: {agent_source_dir}"
        source_public_files = [
            f
            for f in agent_source_dir.glob("nw-*.md")
            if is_public_agent(f.name, public_agents)
        ]
        assert len(source_public_files) >= 1, "No public nw-*.md agent files in source"

        result = plugin.install(install_context)

        assert result.success, f"Installation failed: {result.message}"
        assert target_agents_dir.exists()

        target_files = list(target_agents_dir.glob("nw-*.md"))
        assert len(target_files) == len(source_public_files), (
            f"Expected {len(source_public_files)} public nw-*.md files, "
            f"found {len(target_files)}"
        )

    def test_return_plugin_result_with_correct_public_file_count(
        self, install_context: InstallContext, public_agents: set[str]
    ):
        """
        Given: nWave/agents/ contains public and private agent files
        When: install() is called
        Then: PluginResult reports correct count of public agents only
        """
        plugin = AgentsPlugin()
        source_dir = install_context.project_root / "nWave" / "agents"
        expected_count = len(
            [
                f
                for f in source_dir.glob("nw-*.md")
                if is_public_agent(f.name, public_agents)
            ]
        )

        result = plugin.install(install_context)

        assert isinstance(result, PluginResult)
        assert result.success is True
        assert result.plugin_name == "agents"
        assert f"{expected_count} files" in result.message
        assert result.installed_files is not None
        assert len(result.installed_files) == expected_count

    def test_verify_confirms_agent_files_present_after_install(
        self, install_context: InstallContext
    ):
        """
        Given: install() completed successfully
        When: verify() is called
        Then: PluginResult.success is True with verification count
        """
        plugin = AgentsPlugin()
        install_result = plugin.install(install_context)
        assert install_result.success, f"Install failed: {install_result.message}"

        verify_result = plugin.verify(install_context)

        assert verify_result.success is True
        assert "Agents verification passed" in verify_result.message


# -----------------------------------------------------------------------------
# Verify Error Cases
# -----------------------------------------------------------------------------


def test_agents_plugin_verify_fails_when_target_directory_missing(
    tmp_path: Path, project_root: Path, test_logger: logging.Logger
):
    """AgentsPlugin.verify() should fail when target directory does not exist."""
    empty_claude_dir = tmp_path / ".claude-empty"
    empty_claude_dir.mkdir(parents=True, exist_ok=True)

    context = InstallContext(
        claude_dir=empty_claude_dir,
        scripts_dir=project_root / "scripts" / "install",
        templates_dir=project_root / "nWave" / "templates",
        logger=test_logger,
        project_root=project_root,
        framework_source=project_root / "nWave",
        dry_run=False,
    )

    plugin = AgentsPlugin()
    verify_result = plugin.verify(context)

    assert verify_result.success is False
    assert "target directory does not exist" in verify_result.message


def test_agents_plugin_verify_fails_when_no_agent_files(
    tmp_path: Path, project_root: Path, test_logger: logging.Logger
):
    """AgentsPlugin.verify() should fail when directory exists but has no .md files."""
    claude_dir = tmp_path / ".claude-nofiles"
    agents_dir = claude_dir / "agents" / "nw"
    agents_dir.mkdir(parents=True, exist_ok=True)

    context = InstallContext(
        claude_dir=claude_dir,
        scripts_dir=project_root / "scripts" / "install",
        templates_dir=project_root / "nWave" / "templates",
        logger=test_logger,
        project_root=project_root,
        framework_source=project_root / "nWave",
        dry_run=False,
    )

    plugin = AgentsPlugin()
    verify_result = plugin.verify(context)

    assert verify_result.success is False
    assert "no agent files found" in verify_result.message
