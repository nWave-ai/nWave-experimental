"""
Regression test for DependencyCheck remediation text.

Ensures remediation references the current install path (pipx/uv/nwave-ai)
and does NOT reference the obsolete 'pipenv install' command.

Background: PipenvCheck was removed from the active preflight chain, but the
DependencyCheck.run() remediation still referenced 'pipenv install', misleading
users into using a tool they were never told to install.
"""

from unittest.mock import patch

from scripts.install.preflight_checker import DependencyCheck


class TestDependencyCheckRemediation:
    """Regression tests for DependencyCheck remediation content."""

    def _get_remediation_for_missing_module(self) -> str:
        """Helper: run DependencyCheck with one missing module and return remediation."""
        check = DependencyCheck()
        with patch(
            "scripts.install.preflight_checker.importlib.util.find_spec"
        ) as mock_find_spec:
            mock_find_spec.return_value = None  # Simulate all modules missing
            result = check.run()
        assert result.remediation is not None, (
            "Expected non-None remediation on failure"
        )
        return result.remediation

    def test_remediation_does_not_mention_pipenv_install(self):
        """
        GIVEN: DependencyCheck fails due to missing modules
        WHEN: remediation text is returned
        THEN: it does NOT contain 'pipenv install'

        Regression guard: pipenv was removed from the install path; users must
        never be directed to a tool that nwave-ai no longer uses.
        """
        remediation = self._get_remediation_for_missing_module()
        assert "pipenv install" not in remediation

    def test_remediation_mentions_current_install_path(self):
        """
        GIVEN: DependencyCheck fails due to missing modules
        WHEN: remediation text is returned
        THEN: it references pipx, uv, or 'nwave-ai install' as the current path

        Regression guard: users must be directed to an install mechanism that
        actually exists in the current distribution.
        """
        remediation = self._get_remediation_for_missing_module()
        has_current_path = (
            "pipx" in remediation
            or "uv" in remediation
            or "nwave-ai install" in remediation
        )
        assert has_current_path, (
            f"Remediation must reference pipx, uv, or 'nwave-ai install'. Got:\n{remediation}"
        )
