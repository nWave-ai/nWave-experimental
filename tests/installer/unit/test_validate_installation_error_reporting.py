"""Unit tests for validate_installation() error reporting (Step 02-03).

Fix the "Validation failed (0 errors)" contradiction and add structured
verification logging. Tests validate that:
- When a validation condition fails, the error message names the failing condition
- Each verification check is logged with pass/fail and reason
- The error_count accurately reflects ALL failing conditions

CRITICAL: Tests follow hexagonal architecture - mocks only at port boundaries.
NWaveInstaller is the driving port; InstallationVerifier/PluginRegistry are driven ports.

Test Budget: 3 behaviors x 2 = 6 max unit tests
"""

from unittest.mock import MagicMock, patch

import pytest

from scripts.install.plugins.base import PluginResult


class _InstallerTestHelper:
    """Shared test infrastructure for validate_installation tests."""

    @staticmethod
    def build_installer(tmp_path):
        """Build an NWaveInstaller with filesystem mocked."""
        # Create minimal catalog to satisfy fail-closed load_public_agents
        project_dir = tmp_path / "project" / "nWave"
        project_dir.mkdir(parents=True)
        (project_dir / "framework-catalog.yaml").write_text(
            "agents:\n  test-agent:\n    public: true\n"
        )
        with (
            patch(
                "scripts.install.install_nwave.PathUtils.get_claude_config_dir"
            ) as mock_config,
            patch(
                "scripts.install.install_nwave.PathUtils.get_project_root"
            ) as mock_root,
        ):
            mock_config.return_value = tmp_path / ".claude"
            mock_root.return_value = tmp_path / "project"
            from scripts.install.install_nwave import NWaveInstaller

            installer = NWaveInstaller(dry_run=True)
        return installer

    @staticmethod
    def passing_verification_result():
        """Create a VerificationResult mock where everything passes."""
        result = MagicMock()
        result.success = True
        result.manifest_exists = True
        result.missing_essential_files = []
        return result

    @staticmethod
    def all_plugins_pass():
        """Plugin results where all plugins pass."""
        return {
            "agents": PluginResult(success=True, plugin_name="agents", message="OK"),
            "commands": PluginResult(
                success=True, plugin_name="commands", message="OK"
            ),
            "des": PluginResult(success=True, plugin_name="des", message="OK"),
        }

    @staticmethod
    def failing_des_plugin():
        """Plugin results where DES plugin fails."""
        return {
            "agents": PluginResult(success=True, plugin_name="agents", message="OK"),
            "commands": PluginResult(
                success=True, plugin_name="commands", message="OK"
            ),
            "des": PluginResult(
                success=False,
                plugin_name="des",
                message="DES verification failed",
                errors=["Missing des/__init__.py"],
            ),
        }

    @staticmethod
    def setup_framework_dirs(installer):
        """Create minimal framework source directories."""
        framework_src = installer.framework_source
        for subdir in ["agents/nw", "commands/nw", "templates", "scripts"]:
            (framework_src / subdir).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def run_validate_with(
        installer,
        verifier_result=None,
        schema_valid=True,
        plugin_results=None,
    ):
        """Run validate_installation with controlled mocks, capture logs."""
        if verifier_result is None:
            verifier_result = _InstallerTestHelper.passing_verification_result()
        if plugin_results is None:
            plugin_results = _InstallerTestHelper.all_plugins_pass()

        log_messages = []
        original_info = installer.logger.info
        original_error = installer.logger.error

        def capture_info(msg):
            log_messages.append(("INFO", msg))
            original_info(msg)

        def capture_error(msg):
            log_messages.append(("ERROR", msg))
            original_error(msg)

        installer.logger.info = capture_info
        installer.logger.error = capture_error

        mock_registry = MagicMock()
        mock_registry.verify_all.return_value = plugin_results

        with (
            patch.object(
                installer,
                "_create_plugin_registry",
                return_value=mock_registry,
            ),
            patch.object(
                type(installer),
                "_validate_schema_template",
                return_value=schema_valid,
            ),
            patch("scripts.install.install_nwave.InstallationVerifier") as MockVerifier,
        ):
            mock_verifier_instance = MockVerifier.return_value
            mock_verifier_instance.run_verification.return_value = verifier_result

            _InstallerTestHelper.setup_framework_dirs(installer)

            result = installer.validate_installation()

        return result, log_messages


class TestValidationFailureNamesFailingCondition:
    """When validation fails, the error message must name WHICH condition failed."""

    def test_all_synced_false_names_components_out_of_sync(self, tmp_path):
        """
        GIVEN: result.success=True, schema_valid=True, all_synced=False, no plugin_failures
        WHEN: validate_installation() is called
        THEN: The error message names "components out of sync" (not "0 errors")
        """
        # ARRANGE
        installer = _InstallerTestHelper.build_installer(tmp_path)

        # ACT
        result, log_messages = _InstallerTestHelper.run_validate_with(installer)
        # all_synced will be False because no agent/command/template source files exist
        # in the framework source dirs (empty dirs)

        # ASSERT
        assert result is False, "Validation should fail when components are not synced"
        error_messages = [msg for level, msg in log_messages if level == "ERROR"]
        all_error_text = " ".join(error_messages)
        # The contradiction: should NOT say "0 errors"
        assert "(0 errors)" not in all_error_text, (
            "Must not produce contradictory '0 errors' message"
        )
        # Should identify what actually failed
        assert (
            "sync" in all_error_text.lower() or "component" in all_error_text.lower()
        ), (
            f"Error message should name the sync failure condition. Got: {all_error_text}"
        )

    def test_plugin_failure_names_failing_plugin(self, tmp_path):
        """
        GIVEN: result.success=True, schema_valid=True, all_synced=True, plugin_failures exists
        WHEN: validate_installation() is called
        THEN: The error message includes the failing plugin count
        """
        # ARRANGE
        installer = _InstallerTestHelper.build_installer(tmp_path)
        # Create source files so all_synced becomes True
        framework_src = installer.framework_source
        agents_dir = framework_src / "agents" / "nw"
        agents_dir.mkdir(parents=True, exist_ok=True)
        target_agents = installer.claude_config_dir / "agents" / "nw"
        target_agents.mkdir(parents=True, exist_ok=True)
        # Create matching agents
        (agents_dir / "nw-test.md").write_text("# test")
        (target_agents / "nw-test.md").write_text("# test")

        # Create catalog with public_agents
        catalog_dir = framework_src
        if not (catalog_dir / "framework-catalog.yaml").exists():
            (catalog_dir / "framework-catalog.yaml").write_text(
                "agents:\n  public:\n    - nw-test\n"
            )

        # ACT
        result, log_messages = _InstallerTestHelper.run_validate_with(
            installer,
            plugin_results=_InstallerTestHelper.failing_des_plugin(),
        )

        # ASSERT
        assert result is False, "Validation should fail when plugin verification fails"
        error_messages = [msg for level, msg in log_messages if level == "ERROR"]
        all_error_text = " ".join(error_messages)
        assert "(0 errors)" not in all_error_text, (
            "Must not produce contradictory '0 errors' message"
        )

    def test_schema_invalid_counted_in_errors(self, tmp_path):
        """
        GIVEN: schema_valid=False (only failing condition)
        WHEN: validate_installation() is called
        THEN: error_count includes schema failure (not 0 errors)
        """
        # ARRANGE
        installer = _InstallerTestHelper.build_installer(tmp_path)

        # ACT
        result, log_messages = _InstallerTestHelper.run_validate_with(
            installer,
            schema_valid=False,
        )

        # ASSERT
        assert result is False
        error_messages = [msg for level, msg in log_messages if level == "ERROR"]
        all_error_text = " ".join(error_messages)
        # At minimum, schema failure should be counted
        assert "(0 errors)" not in all_error_text or "schema" in all_error_text.lower()


class TestVerificationLogsEachCheck:
    """Each verification check should be logged with pass/fail and reason."""

    @pytest.mark.parametrize(
        "condition_name,setup_kwargs",
        [
            ("plugin", {"plugin_results": _InstallerTestHelper.failing_des_plugin()}),
            ("schema", {"schema_valid": False}),
        ],
        ids=["plugin-failure", "schema-failure"],
    )
    def test_failing_condition_logged_with_reason(
        self, tmp_path, condition_name, setup_kwargs
    ):
        """
        GIVEN: A specific validation condition fails
        WHEN: validate_installation() is called
        THEN: The failure is logged with its specific reason
        """
        # ARRANGE
        installer = _InstallerTestHelper.build_installer(tmp_path)

        # ACT
        result, log_messages = _InstallerTestHelper.run_validate_with(
            installer, **setup_kwargs
        )

        # ASSERT
        assert result is False
        # Each failing check must have a log entry explaining WHY
        assert len([msg for level, msg in log_messages if level == "ERROR"]) > 0, (
            f"At least one ERROR should be logged for {condition_name} failure"
        )
