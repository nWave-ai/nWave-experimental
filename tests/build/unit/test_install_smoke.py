"""Install-and-import smoke tests for the nwave wheel.

Validates that a wheel installed in a clean venv (no dev deps) produces
a working DES runtime and nwave-ai CLI:

  - DES hook adapter importable via ``python -m``
  - ``from des.adapters.drivers.hooks import claude_code_hook_adapter`` works
  - ``from nwave_ai import cli`` works
  - ``python -m nwave_ai.cli version`` returns a valid version string
  - No ``src.des`` import paths remain in installed code (import rewrite verified)
  - Missing DES module causes detectable failure

Pure validation functions live in scripts/validation/validate_installed_wheel.py.
Tests exercise them against a real wheel installed in a temp venv.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.validation.validate_installed_wheel import (
    check_importable,
    check_module_runnable,
    check_no_src_imports,
    find_site_packages,
    run_install_smoke,
)


# WS-15 P1 re-tier (2026-07-14): a real wheel build (~19.8 s one-shot setup) is an
# artifact-build cost, not a unit-test cost -- it does not belong in the fast-feedback
# `-m "not slow"` tier. Mark the whole module `slow` so pre-commit/pre-push skip it;
# CI's full/slow tier still runs it. Opus-reviewed WS-15 plan, category-7 P1.
pytestmark = pytest.mark.slow


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def built_wheel(shared_wheel: Path) -> Path:
    """The session-shared dev wheel (build-once-share; see root conftest)."""
    return shared_wheel


@pytest.fixture(scope="session")
def installed_venv(shared_wheel_venv: Path) -> Path:
    """The session-shared clean venv with the dev wheel installed via uv."""
    return shared_wheel_venv


@pytest.fixture(scope="session")
def venv_python(installed_venv: Path) -> Path:
    """Return the path to the venv's Python interpreter."""
    return installed_venv / "bin" / "python"


# ---------------------------------------------------------------------------
# Scenario: Full smoke report passes on valid install
# ---------------------------------------------------------------------------


class TestFullSmokeReportPasses:
    """A correctly installed wheel should produce a passing smoke report."""

    def test_run_install_smoke_all_pass(self, venv_python: Path):
        """The full smoke check pipeline returns all-passing results."""
        report = run_install_smoke(venv_python)

        failures = [r for r in report.results if not r.passed]
        assert failures == [], (
            f"Expected all smoke checks to pass, got {len(failures)} failure(s):\n"
            + "\n".join(f"  - [{r.check_name}] {r.message}" for r in failures)
        )


# ---------------------------------------------------------------------------
# Scenario: Missing DES module causes detectable failure
# ---------------------------------------------------------------------------


class TestMissingDesModuleDetected:
    """check_importable must correctly report failure for missing modules."""

    def test_missing_module_detected(self, venv_python: Path):
        """A nonexistent module is correctly flagged as not importable."""
        result = check_importable(venv_python, "des.nonexistent_module_xyz")
        assert not result.passed, (
            "Expected check_importable to fail for nonexistent module"
        )
        assert "nonexistent_module_xyz" in result.message


# ---------------------------------------------------------------------------
# Scenario: Public API return shapes (consolidates 7 redundant tests)
#
# check_importable / check_module_runnable / check_no_src_imports are all
# exercised internally by run_install_smoke (called by TestFullSmokeReportPasses).
# This test validates the public API contracts (return shape, allow_nonzero
# semantics) without duplicating the subprocess work.
# Pattern: nw-test-optimization §3.7 Single-Lifecycle Consolidation + §2.4
# ---------------------------------------------------------------------------


class TestPublicApiDirectCalls:
    """Public check functions return valid CheckResult shapes on happy paths."""

    def test_public_check_functions_return_correct_shapes(self, venv_python: Path):
        """check_importable, check_module_runnable, check_no_src_imports all
        return passing CheckResult instances for a correctly installed wheel."""
        # check_importable -- DES hook adapter
        r1 = check_importable(
            venv_python,
            "des.adapters.drivers.hooks.claude_code_hook_adapter",
        )
        assert r1.passed, f"DES hook adapter not importable: {r1.message}"

        # check_importable -- nwave_ai.cli
        r2 = check_importable(venv_python, "nwave_ai.cli")
        assert r2.passed, f"nwave_ai.cli not importable: {r2.message}"

        # check_module_runnable -- CLI version command
        r3 = check_module_runnable(
            venv_python,
            "nwave_ai.cli",
            args=["version"],
        )
        assert r3.passed, f"nwave-ai version command failed: {r3.message}"

        # check_module_runnable -- hook adapter (allow_nonzero: exits with usage)
        r4 = check_module_runnable(
            venv_python,
            "des.adapters.drivers.hooks.claude_code_hook_adapter",
            args=[],
            allow_nonzero=True,
        )
        assert r4.passed, f"DES hook adapter not runnable as module: {r4.message}"

        # check_no_src_imports -- no src.des references in installed des/ package
        site_packages = find_site_packages(venv_python)
        r5 = check_no_src_imports(site_packages, "des")
        assert r5.passed, f"Found src.des import paths in installed code: {r5.message}"
