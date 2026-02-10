"""
Step definitions for documentation accuracy acceptance tests (AC-10).

These tests verify that installation documentation is accurate and up-to-date.
Some tests are marked @manual as they require human verification on a fresh machine.

Cross-platform compatible (Windows, macOS, Linux).
"""

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when


# Load scenarios from feature files
scenarios("../features/06_documentation.feature")

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent
INSTALLATION_GUIDE = PROJECT_ROOT / "docs" / "installation" / "installation-guide.md"


# ============================================================================
# GIVEN - Preconditions
# ============================================================================


@given("the installation guide exists at docs/installation/installation-guide.md")
def installation_guide_exists():
    """Verify installation guide exists."""
    assert INSTALLATION_GUIDE.exists(), (
        f"Installation guide not found at {INSTALLATION_GUIDE}"
    )


@given("I have a fresh machine with Python installed")
def fresh_machine_with_python():
    """
    Precondition for manual test: fresh machine with Python.

    This is a documentation step for manual testing.
    """
    # This step is for manual test specification
    pass


@given(parsers.parse('pipenv is installed via "{command}"'))
def pipenv_installed_via_command(command):
    """
    Precondition for manual test: pipenv installed.

    This is a documentation step for manual testing.
    """
    # This step is for manual test specification
    assert "pip install pipenv" in command


@given("I read the installation guide prerequisites")
def read_prerequisites():
    """Read the prerequisites section of the installation guide."""
    assert INSTALLATION_GUIDE.exists()
    return INSTALLATION_GUIDE.read_text()


@given("I read the quick start section")
def read_quick_start():
    """Read the quick start section of the installation guide."""
    assert INSTALLATION_GUIDE.exists()
    return INSTALLATION_GUIDE.read_text()


@given("I read the installation guide")
def read_installation_guide():
    """Read the complete installation guide."""
    assert INSTALLATION_GUIDE.exists()
    return INSTALLATION_GUIDE.read_text()


@given("I read the troubleshooting section")
def read_troubleshooting():
    """Read the troubleshooting section of the installation guide."""
    assert INSTALLATION_GUIDE.exists()
    return INSTALLATION_GUIDE.read_text()


# ============================================================================
# WHEN - Actions
# ============================================================================


@when("I follow the quick start instructions:")
def follow_quick_start_instructions(pytestconfig):
    """
    Follow quick start instructions (manual test).

    The table in the feature file specifies the steps to follow.
    This is documented for manual verification.
    """
    # This step is for manual test documentation
    pass


# ============================================================================
# THEN - Assertions
# ============================================================================


@then("each command should succeed")
def each_command_succeeds():
    """
    Verify each command succeeds (manual test).

    This is documented for manual verification.
    """
    # This step is for manual test documentation
    pass


@then("nWave should be installed successfully")
def nwave_installed_successfully():
    """
    Verify nWave is installed successfully (manual test).

    This is documented for manual verification.
    """
    # This step is for manual test documentation
    pass


@then(parsers.parse('the prerequisites should include "{text}"'))
def prerequisites_include(text):
    """Verify prerequisites section includes specified text."""
    content = INSTALLATION_GUIDE.read_text()

    # Look in prerequisites section or general content
    assert text.lower() in content.lower(), f"Prerequisites don't include '{text}'"


@then(parsers.parse('the prerequisites should NOT state "{text}" as minimum'))
def prerequisites_not_state(text):
    """Verify prerequisites don't incorrectly state a requirement."""
    content = INSTALLATION_GUIDE.read_text()

    # Check for incorrect minimum version statement
    # "Python 3.11" should not be stated as the minimum
    # The correct minimum is Python 3.8
    if "Python" in text:
        # Allow mention of the version if it's not stated as minimum
        # But flag if it says "3.11 or higher" or "requires 3.11"
        problematic_patterns = [
            f"Python {text.split()[-1]} or higher",
            f"requires Python {text.split()[-1]}",
            f"Python >= {text.split()[-1]}",
        ]
        for pattern in problematic_patterns:
            assert pattern not in content, (
                f"Documentation incorrectly states '{pattern}'"
            )


@then(parsers.parse('the quick start should include "{text}"'))
def quick_start_includes(text):
    """Verify quick start section includes specified text."""
    content = INSTALLATION_GUIDE.read_text()

    # Handle "or" pattern in text (e.g., "pipenv run" or "pipenv shell")
    if '" or "' in text:
        options = [opt.strip('"') for opt in text.split('" or "')]
        found = any(opt in content for opt in options)
        assert found, f"Quick start doesn't include any of: {options}"
    else:
        assert text in content, f"Quick start doesn't include '{text}'"


@then(parsers.parse('the quick start should NOT show bare "{text}"'))
def quick_start_not_bare_command(text):
    """Verify quick start doesn't show a bare command without proper context."""
    content = INSTALLATION_GUIDE.read_text()

    # Check for the bare command without pipenv prefix
    lines = content.split("\n")
    for line in lines:
        stripped = line.strip()
        # If line starts with the command but doesn't have pipenv prefix
        if stripped.startswith(text) and "pipenv" not in stripped:
            # Allow if it's clearly part of explanation, not instruction
            if not stripped.startswith("#") and not stripped.startswith("```"):
                pytest.fail(f"Quick start shows bare '{text}' without pipenv context")


@then("the guide should mention pipenv is required")
def guide_mentions_pipenv():
    """Verify guide mentions pipenv requirement."""
    content = INSTALLATION_GUIDE.read_text().lower()
    assert "pipenv" in content, "Guide doesn't mention pipenv"
    assert "required" in content or "prerequisite" in content, (
        "Guide doesn't indicate pipenv is required"
    )


@then("the guide should explain how to install pipenv")
def guide_explains_pipenv_install():
    """Verify guide explains how to install pipenv."""
    content = INSTALLATION_GUIDE.read_text()

    has_pipenv_install = (
        "pip install pipenv" in content or "pip3 install pipenv" in content
    )
    assert has_pipenv_install, "Guide doesn't explain how to install pipenv"


@then("the guide should show pipenv commands for installation")
def guide_shows_pipenv_commands():
    """Verify guide shows pipenv commands."""
    content = INSTALLATION_GUIDE.read_text()

    has_pipenv_commands = (
        "pipenv install" in content
        or "pipenv run" in content
        or "pipenv shell" in content
    )
    assert has_pipenv_commands, "Guide doesn't show pipenv commands"


@then(parsers.parse('the section should address "{error_type}"'))
def section_addresses_error(error_type):
    """Verify troubleshooting section addresses specific error."""
    content = INSTALLATION_GUIDE.read_text()
    assert error_type.lower() in content.lower(), (
        f"Troubleshooting doesn't address '{error_type}'"
    )


@then("each error should have a solution with pipenv commands")
def errors_have_pipenv_solutions():
    """Verify error solutions include pipenv commands."""
    content = INSTALLATION_GUIDE.read_text()

    # Check that troubleshooting/error sections include pipenv
    # This is a heuristic check
    has_troubleshooting = (
        "troubleshoot" in content.lower()
        or "error" in content.lower()
        or "problem" in content.lower()
    )
    has_pipenv_solution = "pipenv" in content

    if has_troubleshooting:
        assert has_pipenv_solution, (
            "Troubleshooting section doesn't include pipenv solutions"
        )
