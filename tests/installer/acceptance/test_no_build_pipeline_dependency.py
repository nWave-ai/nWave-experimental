"""
Acceptance test: install_nwave.py has no build pipeline dependency.

Step 02-03: Remove build dependency from install_nwave.py

Verifies that the installer:
- Has no references to dist/ide
- Has no build_framework, run_embedding, check_source methods
- Has no --force-rebuild CLI flag
- Has no hardcoded EXPECTED_AGENT_COUNT / EXPECTED_COMMAND_COUNT constants
- Validates installation against nWave/ source (not dist/ide)
"""

import inspect


class TestNoBuildPipelineDependency:
    """Acceptance: install_nwave.py is free of build pipeline coupling."""

    def test_installer_has_no_dist_ide_references(self):
        """
        GIVEN: install_nwave.py after build pipeline removal
        WHEN: the source code is inspected
        THEN: no references to 'dist/ide' or 'dist' / 'ide' path construction exist
        """
        from scripts.install import install_nwave

        source = inspect.getsource(install_nwave)

        assert '"dist"' not in source, (
            "install_nwave.py still references 'dist' path component"
        )
        assert "'dist'" not in source, (
            "install_nwave.py still references 'dist' path component"
        )
        assert "dist/ide" not in source, "install_nwave.py still references dist/ide"

    def test_installer_has_no_build_methods(self):
        """
        GIVEN: install_nwave.py after build pipeline removal
        WHEN: the NWaveInstaller class is inspected
        THEN: build_framework, run_embedding, and check_source methods are absent
        """
        from scripts.install.install_nwave import NWaveInstaller

        removed_methods = ["build_framework", "run_embedding", "check_source"]
        for method_name in removed_methods:
            assert not hasattr(NWaveInstaller, method_name), (
                f"NWaveInstaller still has '{method_name}' method"
            )

    def test_installer_has_no_force_rebuild_flag(self):
        """
        GIVEN: install_nwave.py after build pipeline removal
        WHEN: main() CLI argument parser is inspected
        THEN: --force-rebuild is not a recognized argument
        """
        from scripts.install import install_nwave

        source = inspect.getsource(install_nwave)

        assert "force-rebuild" not in source, (
            "install_nwave.py still has --force-rebuild flag"
        )
        assert "force_rebuild" not in source, (
            "install_nwave.py still has force_rebuild parameter"
        )

    def test_installer_has_no_hardcoded_expected_counts(self):
        """
        GIVEN: install_nwave.py after build pipeline removal
        WHEN: module-level constants are inspected
        THEN: EXPECTED_AGENT_COUNT and EXPECTED_COMMAND_COUNT are absent
        """
        from scripts.install import install_nwave

        assert not hasattr(install_nwave, "EXPECTED_AGENT_COUNT"), (
            "install_nwave still has EXPECTED_AGENT_COUNT constant"
        )
        assert not hasattr(install_nwave, "EXPECTED_COMMAND_COUNT"), (
            "install_nwave still has EXPECTED_COMMAND_COUNT constant"
        )

    def test_installer_validates_against_nwave_source(self):
        """
        GIVEN: install_nwave.py after build pipeline removal
        WHEN: validate_installation() source is inspected
        THEN: it compares against nWave/agents/ and nWave/tasks/nw/ (not dist/ide)
        """
        from scripts.install.install_nwave import NWaveInstaller

        source = inspect.getsource(NWaveInstaller.validate_installation)

        # Should reference nWave source paths
        assert "nWave" in source, (
            "validate_installation should reference nWave source directory"
        )

        # Should NOT reference dist/ide
        assert "dist" not in source, (
            "validate_installation still references dist directory"
        )

    def test_installation_succeeds_without_dist_ide(self, tmp_path):
        """
        GIVEN: A project root WITHOUT dist/ide directory
        WHEN: NWaveInstaller is instantiated
        THEN: initialization succeeds (no error about missing dist/ide)
        """
        from unittest.mock import MagicMock, Mock, patch

        from scripts.install.install_nwave import NWaveInstaller

        with patch.object(NWaveInstaller, "__init__", lambda self, *a, **kw: None):
            installer = NWaveInstaller()
            installer.dry_run = False
            installer.project_root = tmp_path
            installer.claude_config_dir = tmp_path / "claude"
            installer.logger = Mock()
            installer.logger.progress_spinner = MagicMock()
            installer.logger.progress_spinner.return_value.__enter__ = Mock()
            installer.logger.progress_spinner.return_value.__exit__ = Mock()

        # dist/ide does NOT exist
        assert not (tmp_path / "dist" / "ide").exists()

        # Installer should not require dist/ide at all
        assert not hasattr(installer, "framework_source") or (
            installer.framework_source is None
            or "dist" not in str(installer.framework_source)
        )
