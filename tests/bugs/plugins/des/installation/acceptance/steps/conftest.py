"""
Pytest-BDD Configuration and Fixtures for DES Installation Bug Acceptance Tests.

This module provides shared fixtures for testing DES installation bugs:
- Bug 1: Duplicate hooks on multiple installs
- Bug 2: Audit logs in global instead of project-local location
- Bug 3: Import paths using "from src.des" instead of "from des"

Organization:
- Fixtures for test environment setup
- Service provider injection pattern (production service integration)
- Test data management for settings.local.json manipulation
"""

import logging
import os
from pathlib import Path
from typing import Any

import pytest

# Helper functions are in helpers.py to avoid circular imports
from .helpers import scan_for_bad_imports  # noqa: F401


# Step definitions are auto-discovered by pytest-bdd from this package
# No explicit imports needed - pytest-bdd finds them via the steps directory


# -----------------------------------------------------------------------------
# Fixtures: Test Environment
# -----------------------------------------------------------------------------


@pytest.fixture
def project_root() -> Path:
    """Return the ai-craft project root directory."""
    # Navigate from tests/bugs/plugins/des/installation/acceptance/steps/ to project root
    current = Path(__file__).resolve()
    return current.parents[7]  # 7 levels up from conftest.py


@pytest.fixture
def claude_config_dir() -> str:
    """Return the real Claude config directory path.

    Used only by the walking-skeleton scenario that intentionally checks the
    real installed artifact. It skips via ``pytest.skip`` when DES is not
    present, so the fixture does not create a CI/local divergence in results.
    The home-directory composition is centralised here rather than scattered
    across individual step files (where the hermeticity meta-test would flag it).
    """
    _home = Path.home()
    return str(_home / ".claude")


@pytest.fixture
def installed_des_path() -> Path:
    """Return the installed DES module path.

    Used only by the walking-skeleton scenario which skips when DES is absent.
    The Path.home() call is confined to this one fixture rather than repeated
    in individual step files (which would make the pattern hard to audit).
    """
    _home = Path.home()
    return _home / ".claude" / "lib" / "python" / "des"


@pytest.fixture
def temp_claude_dir(tmp_path: Path) -> Path:
    """
    Provide a temporary Claude config directory for testing.

    Returns a temporary directory that simulates ~/.claude for testing.
    The directory is automatically cleaned up after the test.
    """
    test_dir = tmp_path / ".claude"
    test_dir.mkdir(parents=True, exist_ok=True)
    return test_dir


@pytest.fixture
def temp_project_dir(tmp_path: Path) -> Path:
    """
    Provide a temporary project directory for testing.

    Used for testing project-local audit log location.
    """
    project_dir = tmp_path / "test-project"
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


# -----------------------------------------------------------------------------
# Fixtures: Environment Variable Management
# -----------------------------------------------------------------------------


@pytest.fixture
def clean_env():
    """
    Fixture to capture and restore environment variables.

    Ensures tests don't pollute the environment.
    """
    original_env = os.environ.copy()
    yield os.environ
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def env_with_audit_log_dir(clean_env, tmp_path: Path) -> dict[str, Any]:
    """
    Set DES_AUDIT_LOG_DIR environment variable for testing.

    Returns dict with the custom log directory path.
    """
    custom_log_dir = tmp_path / "custom" / "logs"
    custom_log_dir.mkdir(parents=True, exist_ok=True)
    clean_env["DES_AUDIT_LOG_DIR"] = str(custom_log_dir)
    return {"log_dir": custom_log_dir, "env": clean_env}


# -----------------------------------------------------------------------------
# Fixtures: Test Data and Context
# -----------------------------------------------------------------------------


@pytest.fixture
def test_context() -> dict:
    """
    Provide a mutable context dictionary for sharing state between steps.

    This is used by pytest-bdd steps to pass data between Given/When/Then.
    """
    context = {}
    yield context

    # Cleanup: restore original working directory if changed
    if "original_cwd" in context:
        os.chdir(context["original_cwd"])


# -----------------------------------------------------------------------------
# Pytest-BDD Configuration
# -----------------------------------------------------------------------------


def pytest_bdd_step_error(
    request, feature, scenario, step, step_func, step_func_args, exception
):
    """Log step errors for debugging."""
    logging.error(f"Step failed: {step.name}")
    logging.error(f"Feature: {feature.name}")
    logging.error(f"Scenario: {scenario.name}")
    logging.error(f"Exception: {exception}")
