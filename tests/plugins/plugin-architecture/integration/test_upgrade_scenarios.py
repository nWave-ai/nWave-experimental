"""
Integration tests for upgrade scenarios (step 04-03).

Test upgrade from monolithic installer (v1.2.0) to plugin-based (v1.3.0+).
Ensure existing installations are preserved.

Domain: Plugin Infrastructure - Upgrade Compatibility
"""

import logging
from pathlib import Path

import pytest

from scripts.install.plugins.agents_plugin import AgentsPlugin
from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.commands_plugin import CommandsPlugin
from scripts.install.plugins.des_plugin import DESPlugin
from scripts.install.plugins.registry import PluginRegistry
from scripts.install.plugins.templates_plugin import TemplatesPlugin
from scripts.install.plugins.utilities_plugin import UtilitiesPlugin


# -----------------------------------------------------------------------------
# Test Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def test_logger() -> logging.Logger:
    """Provide a configured logger for test execution."""
    logger = logging.getLogger("test.upgrade_scenarios")
    logger.setLevel(logging.DEBUG)
    return logger


@pytest.fixture
def project_root() -> Path:
    """Return the nWave project root directory."""
    current = Path(__file__).resolve()
    return current.parents[4]  # 4 levels up from test file


@pytest.fixture
def clean_test_directory(tmp_path: Path) -> Path:
    """Provide a clean test installation directory simulating ~/.claude."""
    test_dir = tmp_path / ".claude"
    test_dir.mkdir(parents=True, exist_ok=True)
    return test_dir


@pytest.fixture
def install_context(clean_test_directory, project_root, test_logger):
    """Create InstallContext for testing."""
    return InstallContext(
        claude_dir=clean_test_directory,
        scripts_dir=project_root / "scripts" / "install",
        templates_dir=project_root / "nWave" / "templates",
        logger=test_logger,
        project_root=project_root,
        framework_source=project_root / "dist" / "ide",
        dry_run=False,
    )


@pytest.fixture
def simulated_v120_installation(clean_test_directory: Path, project_root: Path) -> Path:
    """
    Simulate an existing v1.2.0 monolithic installation.

    Creates the directory structure and files that would exist after
    a successful v1.2.0 monolithic installer run.

    Returns the claude_dir path for the simulated installation.
    """
    claude_dir = clean_test_directory

    # Create agents directory with some agent files
    agents_dir = claude_dir / "agents" / "nw"
    agents_dir.mkdir(parents=True, exist_ok=True)

    # Create sample agent files (simulating monolithic installation)
    sample_agents = ["software-crafter.md", "solution-architect.md", "researcher.md"]
    for agent_name in sample_agents:
        agent_file = agents_dir / agent_name
        agent_file.write_text(f"# {agent_name}\n\nMonolithic v1.2.0 installation\n")

    # Create commands directory with command files
    commands_dir = claude_dir / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)

    sample_commands = ["atdd.md", "root-why.md", "commit.md"]
    for cmd_name in sample_commands:
        cmd_file = commands_dir / cmd_name
        cmd_file.write_text(f"# {cmd_name}\n\nCommand from v1.2.0\n")

    # Create templates directory with template files
    templates_dir = claude_dir / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)

    sample_templates = [
        "develop-outside-in-tdd.yaml",
        "nwave-complete-methodology.yaml",
    ]
    for template_name in sample_templates:
        template_file = templates_dir / template_name
        template_file.write_text(f"# {template_name}\nversion: 1.2.0\n")

    # Create scripts directory with utility scripts
    scripts_dir = claude_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    utility_script = scripts_dir / "validate_step_file.py"
    utility_script.write_text('"""Utility script v1.2.0."""\n__version__ = "1.2.0"\n')

    # Create version marker (simulating monolithic installation marker)
    version_file = claude_dir / ".nwave_version"
    version_file.write_text("1.2.0")

    return claude_dir


# -----------------------------------------------------------------------------
# Test Class: Upgrade Scenario - Existing Components Preserved
# -----------------------------------------------------------------------------


class TestExistingComponentsPreservedDuringUpgrade:
    """
    Integration tests for verifying existing components are preserved
    during upgrade from monolithic v1.2.0 to plugin-based v1.3.0+.
    """

    def test_existing_agents_detected_before_upgrade(
        self,
        simulated_v120_installation: Path,
        project_root: Path,
        test_logger: logging.Logger,
    ):
        """
        Existing components should be detected before upgrade.

        Given: v1.2.0 monolithic installation exists
        When: Plugin-based installer scans the installation
        Then: Existing agent files are detected
        """
        # Arrange - simulated installation already created by fixture
        agents_dir = simulated_v120_installation / "agents" / "nw"

        # Assert - existing agents are present before upgrade
        assert agents_dir.exists(), (
            "Agents directory should exist in v1.2.0 installation"
        )
        existing_agents = list(agents_dir.glob("*.md"))
        assert len(existing_agents) == 3, (
            f"Expected 3 agent files from v1.2.0, found {len(existing_agents)}"
        )

    def test_existing_agents_preserved_after_plugin_installation(
        self,
        simulated_v120_installation: Path,
        project_root: Path,
        test_logger: logging.Logger,
    ):
        """
        Existing agent files should be preserved or upgraded after plugin installation.

        Given: v1.2.0 monolithic installation with 3 agents
        When: AgentsPlugin.install() runs
        Then: Agents are present (existing preserved or upgraded)
        """
        # Arrange
        context = InstallContext(
            claude_dir=simulated_v120_installation,
            scripts_dir=project_root / "scripts" / "install",
            templates_dir=project_root / "nWave" / "templates",
            logger=test_logger,
            project_root=project_root,
            framework_source=project_root / "dist" / "ide",
            dry_run=False,
        )

        agents_dir = simulated_v120_installation / "agents" / "nw"
        pre_upgrade_count = len(list(agents_dir.glob("*.md")))

        # Act
        plugin = AgentsPlugin()
        result = plugin.install(context)

        # Assert
        assert result.success, f"AgentsPlugin installation failed: {result.message}"

        post_upgrade_agents = list(agents_dir.glob("*.md"))
        assert len(post_upgrade_agents) >= pre_upgrade_count, (
            f"Expected at least {pre_upgrade_count} agents after upgrade, "
            f"found {len(post_upgrade_agents)}"
        )

    def test_existing_commands_preserved_after_plugin_installation(
        self,
        simulated_v120_installation: Path,
        project_root: Path,
        test_logger: logging.Logger,
    ):
        """
        Existing command files should be preserved after plugin installation.

        Given: v1.2.0 monolithic installation with 3 commands
        When: CommandsPlugin.install() runs
        Then: Commands are present (existing preserved or upgraded)
        """
        # Arrange
        context = InstallContext(
            claude_dir=simulated_v120_installation,
            scripts_dir=project_root / "scripts" / "install",
            templates_dir=project_root / "nWave" / "templates",
            logger=test_logger,
            project_root=project_root,
            framework_source=project_root / "dist" / "ide",
            dry_run=False,
        )

        commands_dir = simulated_v120_installation / "commands"
        pre_upgrade_count = len(list(commands_dir.glob("*.md")))

        # Act
        plugin = CommandsPlugin()
        result = plugin.install(context)

        # Assert
        assert result.success, f"CommandsPlugin installation failed: {result.message}"

        post_upgrade_commands = list(commands_dir.glob("*.md"))
        assert len(post_upgrade_commands) >= pre_upgrade_count, (
            f"Expected at least {pre_upgrade_count} commands after upgrade, "
            f"found {len(post_upgrade_commands)}"
        )


# -----------------------------------------------------------------------------
# Test Class: Upgrade Scenario - DES Plugin Addition
# -----------------------------------------------------------------------------


class TestDESPluginAddedDuringUpgrade:
    """
    Integration tests for verifying DES plugin can be added to existing
    installation without affecting existing components.
    """

    def test_des_plugin_added_to_existing_installation(
        self,
        simulated_v120_installation: Path,
        project_root: Path,
        test_logger: logging.Logger,
    ):
        """
        DES plugin should be added to existing installation.

        Given: v1.2.0 installation exists (without DES)
        When: Full plugin-based installation runs (with DES)
        Then: DES components are added without breaking existing installation
        """
        # Arrange
        context = InstallContext(
            claude_dir=simulated_v120_installation,
            scripts_dir=project_root / "scripts" / "install",
            templates_dir=project_root / "nWave" / "templates",
            logger=test_logger,
            project_root=project_root,
            framework_source=project_root / "dist" / "ide",
            dry_run=False,
        )

        registry = PluginRegistry()
        registry.register(AgentsPlugin())
        registry.register(CommandsPlugin())
        registry.register(TemplatesPlugin())
        registry.register(UtilitiesPlugin())
        registry.register(DESPlugin())

        # Capture pre-upgrade state
        agents_dir = simulated_v120_installation / "agents" / "nw"
        pre_upgrade_agent_count = len(list(agents_dir.glob("*.md")))

        # Act
        results = registry.install_all(context)

        # Assert - DES was added
        assert "des" in results, "DES plugin should be in results"
        assert results["des"].success, (
            f"DES installation failed: {results['des'].message}"
        )

        # Assert - existing components preserved
        post_upgrade_agent_count = len(list(agents_dir.glob("*.md")))
        assert post_upgrade_agent_count >= pre_upgrade_agent_count, (
            "Existing agents should be preserved after DES addition"
        )

    def test_des_plugin_does_not_modify_existing_agents(
        self,
        simulated_v120_installation: Path,
        project_root: Path,
        test_logger: logging.Logger,
    ):
        """
        DES plugin installation should not modify existing agent files.

        Given: v1.2.0 installation with specific agent content
        When: DES plugin installed
        Then: Agent files are either unchanged or upgraded (not corrupted)
        """
        # Arrange
        context = InstallContext(
            claude_dir=simulated_v120_installation,
            scripts_dir=project_root / "scripts" / "install",
            templates_dir=project_root / "nWave" / "templates",
            logger=test_logger,
            project_root=project_root,
            framework_source=project_root / "dist" / "ide",
            dry_run=False,
        )

        # First install base plugins
        registry = PluginRegistry()
        registry.register(AgentsPlugin())
        registry.register(CommandsPlugin())
        registry.register(TemplatesPlugin())
        registry.register(UtilitiesPlugin())

        _base_results = registry.install_all(context)

        # Capture agent state after base installation
        agents_dir = simulated_v120_installation / "agents" / "nw"
        agent_files_before_des = {f.name for f in agents_dir.glob("*.md")}

        # Now add DES plugin separately
        des_plugin = DESPlugin()
        des_result = des_plugin.install(context)

        # Assert - DES installed successfully
        assert des_result.success, f"DES installation failed: {des_result.message}"

        # Assert - agent files unchanged
        agent_files_after_des = {f.name for f in agents_dir.glob("*.md")}
        assert agent_files_before_des == agent_files_after_des, (
            "DES plugin should not modify agent files"
        )


# -----------------------------------------------------------------------------
# Test Class: Upgrade Scenario - Verification After Upgrade
# -----------------------------------------------------------------------------


class TestVerificationPassesAfterUpgrade:
    """
    Integration tests for verifying that verification passes for all
    components after upgrade from monolithic to plugin-based installer.
    """

    def test_all_plugins_verify_after_full_upgrade(
        self,
        simulated_v120_installation: Path,
        project_root: Path,
        test_logger: logging.Logger,
    ):
        """
        All plugins should verify successfully after full upgrade.

        Given: v1.2.0 monolithic installation
        When: Full plugin-based upgrade completes
        Then: All plugins verify successfully
        """
        # Arrange
        context = InstallContext(
            claude_dir=simulated_v120_installation,
            scripts_dir=project_root / "scripts" / "install",
            templates_dir=project_root / "nWave" / "templates",
            logger=test_logger,
            project_root=project_root,
            framework_source=project_root / "dist" / "ide",
            dry_run=False,
        )

        registry = PluginRegistry()
        registry.register(AgentsPlugin())
        registry.register(CommandsPlugin())
        registry.register(TemplatesPlugin())
        registry.register(UtilitiesPlugin())
        registry.register(DESPlugin())

        # Act - Install all plugins
        install_results = registry.install_all(context)

        # Verify all installed successfully
        for plugin_name, result in install_results.items():
            assert result.success, (
                f"Plugin '{plugin_name}' installation failed: {result.message}"
            )

        # Act - Verify all plugins
        verify_results = registry.verify_all(context)

        # Assert - all verify successfully
        for plugin_name, result in verify_results.items():
            assert result.success, (
                f"Plugin '{plugin_name}' verification failed: {result.message}\n"
                f"Errors: {result.errors}"
            )

    def test_agents_plugin_verifies_after_upgrade(
        self,
        simulated_v120_installation: Path,
        project_root: Path,
        test_logger: logging.Logger,
    ):
        """
        AgentsPlugin should verify successfully after upgrade.

        Given: v1.2.0 installation upgraded with AgentsPlugin
        When: AgentsPlugin.verify() is called
        Then: Verification passes
        """
        # Arrange
        context = InstallContext(
            claude_dir=simulated_v120_installation,
            scripts_dir=project_root / "scripts" / "install",
            templates_dir=project_root / "nWave" / "templates",
            logger=test_logger,
            project_root=project_root,
            framework_source=project_root / "dist" / "ide",
            dry_run=False,
        )

        plugin = AgentsPlugin()

        # Act - Install
        install_result = plugin.install(context)
        assert install_result.success, f"Installation failed: {install_result.message}"

        # Act - Verify
        verify_result = plugin.verify(context)

        # Assert
        assert verify_result.success, (
            f"AgentsPlugin verification failed after upgrade: {verify_result.message}"
        )

    def test_des_plugin_verifies_after_addition_to_existing_installation(
        self,
        simulated_v120_installation: Path,
        project_root: Path,
        test_logger: logging.Logger,
    ):
        """
        DESPlugin should verify successfully when added to existing installation.

        Given: v1.2.0 installation with base plugins upgraded
        When: DES plugin is added and verify() is called
        Then: DES verification passes
        """
        # Arrange
        context = InstallContext(
            claude_dir=simulated_v120_installation,
            scripts_dir=project_root / "scripts" / "install",
            templates_dir=project_root / "nWave" / "templates",
            logger=test_logger,
            project_root=project_root,
            framework_source=project_root / "dist" / "ide",
            dry_run=False,
        )

        # Install base plugins first (DES dependencies)
        registry = PluginRegistry()
        registry.register(AgentsPlugin())
        registry.register(CommandsPlugin())
        registry.register(TemplatesPlugin())
        registry.register(UtilitiesPlugin())
        registry.register(DESPlugin())

        # Act - Install all
        install_results = registry.install_all(context)

        # Assert DES installed
        assert install_results["des"].success, (
            f"DES installation failed: {install_results['des'].message}"
        )

        # Act - Verify DES
        des_plugin = DESPlugin()
        verify_result = des_plugin.verify(context)

        # Assert
        assert verify_result.success, (
            f"DES verification failed after upgrade: {verify_result.message}\n"
            f"Errors: {verify_result.errors}"
        )


# -----------------------------------------------------------------------------
# Test Class: Upgrade Scenario - No Functionality Broken
# -----------------------------------------------------------------------------


class TestNoFunctionalityBrokenAfterUpgrade:
    """
    Integration tests for verifying that no existing functionality is broken
    after upgrade from monolithic to plugin-based installer.
    """

    def test_agent_files_readable_after_upgrade(
        self,
        simulated_v120_installation: Path,
        project_root: Path,
        test_logger: logging.Logger,
    ):
        """
        Agent files should be readable after upgrade.

        Given: v1.2.0 installation upgraded with plugin-based installer
        When: Agent files are read
        Then: All files are valid and readable
        """
        # Arrange
        context = InstallContext(
            claude_dir=simulated_v120_installation,
            scripts_dir=project_root / "scripts" / "install",
            templates_dir=project_root / "nWave" / "templates",
            logger=test_logger,
            project_root=project_root,
            framework_source=project_root / "dist" / "ide",
            dry_run=False,
        )

        plugin = AgentsPlugin()
        install_result = plugin.install(context)
        assert install_result.success

        # Act - Read all agent files
        agents_dir = simulated_v120_installation / "agents" / "nw"
        agent_files = list(agents_dir.glob("*.md"))

        # Assert - all files readable
        for agent_file in agent_files:
            try:
                content = agent_file.read_text(encoding="utf-8")
                assert len(content) > 0, f"Agent file {agent_file.name} is empty"
            except Exception as e:
                pytest.fail(f"Agent file {agent_file.name} not readable: {e}")

    def test_template_files_readable_after_upgrade(
        self,
        simulated_v120_installation: Path,
        project_root: Path,
        test_logger: logging.Logger,
    ):
        """
        Template files should be readable after upgrade.

        Given: v1.2.0 installation upgraded with plugin-based installer
        When: Template files are read
        Then: All files are valid and readable
        """
        # Arrange
        context = InstallContext(
            claude_dir=simulated_v120_installation,
            scripts_dir=project_root / "scripts" / "install",
            templates_dir=project_root / "nWave" / "templates",
            logger=test_logger,
            project_root=project_root,
            framework_source=project_root / "dist" / "ide",
            dry_run=False,
        )

        plugin = TemplatesPlugin()
        install_result = plugin.install(context)
        assert install_result.success

        # Act - Read all template files
        templates_dir = simulated_v120_installation / "templates"
        template_files = list(templates_dir.glob("*.yaml")) + list(
            templates_dir.glob("*.md")
        )

        # Assert - all files readable
        for template_file in template_files:
            try:
                content = template_file.read_text(encoding="utf-8")
                assert len(content) > 0, f"Template file {template_file.name} is empty"
            except Exception as e:
                pytest.fail(f"Template file {template_file.name} not readable: {e}")

    def test_installation_order_respected_during_upgrade(
        self,
        simulated_v120_installation: Path,
        project_root: Path,
        test_logger: logging.Logger,
    ):
        """
        Plugin installation order should be respected during upgrade.

        Given: v1.2.0 installation
        When: Plugin registry installs all plugins
        Then: Plugins are installed in priority order (agents, commands, templates, utilities, des)
        """
        # Arrange - only testing execution order, not actual installation
        registry = PluginRegistry()
        # Register in random order
        registry.register(DESPlugin())
        registry.register(TemplatesPlugin())
        registry.register(AgentsPlugin())
        registry.register(UtilitiesPlugin())
        registry.register(CommandsPlugin())

        # Act
        execution_order = registry.get_execution_order()

        # Assert - proper order
        expected_order = ["agents", "commands", "templates", "utilities", "des"]
        assert execution_order == expected_order, (
            f"Expected order {expected_order}, got {execution_order}"
        )
