"""Preflight checker for nWave installer environment validation.

This module validates the execution environment before any installation action.
Virtual environment detection is a hard requirement that cannot be bypassed.

The preflight checker follows a chain-of-checks pattern where each check
returns a CheckResult with pass/fail status, error code, message, and
remediation instructions.

Usage:
    from scripts.install.preflight_checker import PreflightChecker

    checker = PreflightChecker()
    results = checker.run_all_checks()
    if not all(r.passed for r in results):
        # Handle failures
"""

import importlib.util
import os
import shutil
import sys
from dataclasses import dataclass


try:
    from scripts.install.error_codes import DEP_MISSING, ENV_NO_PIPENV, ENV_NO_VENV
except ImportError:
    from error_codes import DEP_MISSING, ENV_NO_PIPENV, ENV_NO_VENV


# Required modules for nWave installer functionality
REQUIRED_MODULES: list[str] = [
    "yaml",  # For configuration file parsing (PyYAML)
    "pathlib",  # For path handling (stdlib, but verify availability)
]

# Path markers that identify tool-managed virtual environments.
# Used by is_virtual_environment() as a fallback when env vars are stripped.
TOOL_VENV_PATH_MARKERS: tuple[str, ...] = (
    "/uv/tools/",
    "/pipx/venvs/",
    "/.virtualenvs/",
)


@dataclass
class CheckResult:
    """Result of a single preflight check.

    Attributes:
        passed: Whether the check passed successfully.
        error_code: Error code from error_codes module (None if passed).
        message: Human-readable description of the check result.
        remediation: Instructions to fix the issue (None if passed).
    """

    passed: bool
    error_code: str | None
    message: str
    remediation: str | None


def detect_install_tool() -> str | None:
    """Detect which install tool (uv or pipx) is available on PATH.

    Checks for uv first (recommended), then pipx, then returns None
    if neither is found.

    Returns:
        "uv" if uv is on PATH, "pipx" if pipx is on PATH (and uv is not),
        or None if neither is available.
    """
    if shutil.which("uv"):
        return "uv"
    if shutil.which("pipx"):
        return "pipx"
    return None


def _build_remediation(tool: str | None) -> str:
    """Build a tool-aware remediation message for VirtualEnvironmentCheck.

    Args:
        tool: The detected install tool ("uv", "pipx", or None).

    Returns:
        A remediation string matching the user's actual install tool.
    """
    if tool == "uv":
        return (
            "Install nwave-ai using uv (recommended):\n"
            "  uv tool install nwave-ai\n"
            "  nwave-ai install"
        )
    if tool == "pipx":
        return (
            "Install nwave-ai using pipx:\n  pipx install nwave-ai\n  nwave-ai install"
        )
    return (
        "Install uv first (recommended package manager for nwave-ai):\n"
        "  curl -LsSf https://astral.sh/uv/install.sh | sh\n"
        "Then install nwave-ai:\n"
        "  uv tool install nwave-ai\n"
        "  nwave-ai install"
    )


def is_virtual_environment() -> bool:
    """Detect if running inside a Python virtual environment.

    Checks 4 conditions in priority order (most-reliable first):

    1. VIRTUAL_ENV env var: set by venv/virtualenv activation scripts and
       by pipx when the tool subprocess inherits the environment.
    2. UV_TOOL_ENV env var: set by uv when running a tool in its managed
       environment (uv tool run / uv tool install).
    3. sys.prefix != sys.base_prefix: standard detection for activated venvs.
    4. sys.executable path patterns: fallback when env vars are stripped by
       the calling process. Matches uv (/uv/tools/), pipx (/pipx/venvs/),
       and legacy virtualenv (/.virtualenvs/) layouts.
       Note: path normalised to forward slashes for Windows compatibility.

    Returns:
        True if in a virtual environment, False otherwise.
    """
    if "VIRTUAL_ENV" in os.environ:
        return True
    if "UV_TOOL_ENV" in os.environ:
        return True
    if sys.prefix != sys.base_prefix:
        return True
    exe = (sys.executable or "").replace("\\", "/")
    return any(marker in exe for marker in TOOL_VENV_PATH_MARKERS)


class VirtualEnvironmentCheck:
    """Check that the installer is running inside a virtual environment.

    This is a hard requirement that cannot be bypassed. Installing nWave
    outside a virtual environment could pollute the system Python and
    cause dependency conflicts.
    """

    def run(self) -> CheckResult:
        """Execute the virtual environment check.

        Returns:
            CheckResult with pass/fail status and remediation if needed.
        """
        if is_virtual_environment():
            return CheckResult(
                passed=True,
                error_code=None,
                message="Virtual environment detected.",
                remediation=None,
            )

        return CheckResult(
            passed=False,
            error_code=ENV_NO_VENV,
            message="Not running in a virtual environment.",
            remediation=_build_remediation(detect_install_tool()),
        )


class PipenvCheck:
    """Check that pipenv is available for dependency management.

    DEPRECATED: PipenvCheck is no longer included in the active preflight
    check chain (see PreflightChecker._checks). nwave-ai is now distributed
    via pipx/uv and no longer requires pipenv at runtime. This class is
    retained because existing tests import it; it will be removed in a
    future cleanup once those tests are retired.
    """

    def run(self) -> CheckResult:
        """Execute the pipenv availability check.

        Returns:
            CheckResult with pass/fail status and remediation if needed.
        """
        if shutil.which("pipenv") is not None:
            return CheckResult(
                passed=True,
                error_code=None,
                message="Pipenv is available.",
                remediation=None,
            )

        return CheckResult(
            passed=False,
            error_code=ENV_NO_PIPENV,
            message="Pipenv is not installed or not available on PATH.",
            remediation=(
                "Install pipenv to manage dependencies:\n"
                "  pipx install pipenv  # Recommended: isolated installation\n"
                "  # Or: brew install pipenv  (macOS)\n"
                "  # Or: sudo apt install pipenv  (Debian/Ubuntu)\n"
                "For more information: https://pipenv.pypa.io/en/latest/installation/"
            ),
        )


class DependencyCheck:
    """Check that all required Python modules are available.

    This check verifies that modules needed by the nWave installer are
    importable before the build phase begins. It reports ALL missing
    modules in a single pass, not just the first one found.

    Uses importlib.util.find_spec() for module detection without actually
    importing the modules, which avoids side effects during preflight.
    """

    def run(self) -> CheckResult:
        """Execute the dependency verification check.

        Returns:
            CheckResult with pass/fail status and list of missing modules.
        """
        missing_modules: list[str] = []

        for module_name in REQUIRED_MODULES:
            spec = importlib.util.find_spec(module_name)
            if spec is None:
                missing_modules.append(module_name)

        if not missing_modules:
            return CheckResult(
                passed=True,
                error_code=None,
                message="All required dependencies are available.",
                remediation=None,
            )

        # Build message listing ALL missing modules
        missing_list = ", ".join(missing_modules)
        return CheckResult(
            passed=False,
            error_code=DEP_MISSING,
            message=f"Missing required dependencies: {missing_list}",
            remediation=(
                "Re-run `nwave-ai install` to regenerate the install environment.\n"
                "\n"
                "If this persists, reinstall nwave-ai:\n"
                "  pipx reinstall nwave-ai\n"
                "  # Or, if you use uv:\n"
                "  uv tool install --reinstall nwave-ai"
            ),
        )


class PreflightChecker:
    """Orchestrates all preflight checks before installation.

    The checker runs a chain of validation checks in order. Virtual
    environment check is always first and cannot be bypassed even
    with skip_checks flag.

    Usage:
        checker = PreflightChecker()
        results = checker.run_all_checks()
        if checker.has_blocking_failures(results):
            # Installation cannot proceed
    """

    def __init__(self) -> None:
        """Initialize the preflight checker with the chain of checks."""
        self._checks = [
            VirtualEnvironmentCheck(),
            DependencyCheck(),
        ]

    def run_all_checks(self, skip_checks: bool = False) -> list[CheckResult]:
        """Run all preflight checks.

        Args:
            skip_checks: If True, skip optional checks. NOTE: Virtual
                environment check is NEVER skipped as it is a hard
                requirement.

        Returns:
            List of CheckResult objects, one per check executed.
        """
        results: list[CheckResult] = []

        for check in self._checks:
            # Virtual environment check is ALWAYS run and cannot be skipped
            if isinstance(check, VirtualEnvironmentCheck):
                results.append(check.run())
            elif not skip_checks:
                # Other checks can be skipped if skip_checks is True
                results.append(check.run())

        return results

    def has_blocking_failures(self, results: list[CheckResult]) -> bool:
        """Check if any results contain blocking failures.

        Args:
            results: List of CheckResult objects from run_all_checks.

        Returns:
            True if any check failed, False if all passed.
        """
        return any(not result.passed for result in results)

    def get_failed_checks(self, results: list[CheckResult]) -> list[CheckResult]:
        """Get only the failed check results.

        Args:
            results: List of CheckResult objects from run_all_checks.

        Returns:
            List of CheckResult objects that have passed=False.
        """
        return [result for result in results if not result.passed]
