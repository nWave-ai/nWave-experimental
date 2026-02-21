"""Shared fixtures for release train tests.

Provides mock GitHub API responses and common test data
for ci_gate, next_version, trace_message, and patch_pyproject tests.
"""

import pytest


# ---------------------------------------------------------------------------
# GitHub API: Check Runs responses
# ---------------------------------------------------------------------------

SAMPLE_SHA = "abc123def456789012345678901234567890abcd"
SAMPLE_REPO = "Undeadgrishnackh/crafter-ai"


def _make_check_runs_response(check_runs: list[dict]) -> dict:
    """Build a GitHub Check Runs API response."""
    return {
        "total_count": len(check_runs),
        "check_runs": check_runs,
    }


def _make_check_run(
    name: str,
    status: str = "completed",
    conclusion: str | None = "success",
) -> dict:
    """Build a single check-run entry."""
    return {
        "id": 1,
        "name": name,
        "status": status,
        "conclusion": conclusion,
        "html_url": f"https://github.com/{SAMPLE_REPO}/actions/runs/12345",
    }


@pytest.fixture()
def all_green_response() -> dict:
    """All CI check-runs passed (green)."""
    return _make_check_runs_response(
        [
            _make_check_run("CI Pipeline", "completed", "success"),
            _make_check_run("Lint", "completed", "success"),
            _make_check_run("Type Check", "completed", "success"),
        ]
    )


@pytest.fixture()
def one_failed_response() -> dict:
    """One CI check-run failed."""
    return _make_check_runs_response(
        [
            _make_check_run("CI Pipeline", "completed", "failure"),
            _make_check_run("Lint", "completed", "success"),
        ]
    )


@pytest.fixture()
def one_pending_response() -> dict:
    """One CI check-run still in progress."""
    return _make_check_runs_response(
        [
            _make_check_run("CI Pipeline", "in_progress", None),
            _make_check_run("Lint", "completed", "success"),
        ]
    )


@pytest.fixture()
def no_check_runs_response() -> dict:
    """No CI check-runs found for the commit."""
    return _make_check_runs_response([])


@pytest.fixture()
def self_referencing_response() -> dict:
    """Response includes the calling workflow's own check-run (should be excluded)."""
    return _make_check_runs_response(
        [
            _make_check_run("CI Pipeline", "completed", "success"),
            _make_check_run("release-dev", "completed", "success"),
        ]
    )


# ---------------------------------------------------------------------------
# Sample pyproject.toml content
# ---------------------------------------------------------------------------

SAMPLE_PYPROJECT = """\
[project]
name = "nwave"
version = "1.1.21"
description = "nWave Framework"
authors = [
    {name = "Mike", email = "mike@example.com"},
]

[project.urls]
Homepage = "https://github.com/nwave-ai/nwave"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["nWave"]

[tool.nwave]
public_version_floor = "1.1.0"

[tool.semantic_release]
version_variable = "pyproject.toml:version"

[tool.pytest.ini_options]
testpaths = ["tests"]
"""


@pytest.fixture()
def sample_pyproject_content() -> str:
    """A realistic pyproject.toml for patching tests."""
    return SAMPLE_PYPROJECT


@pytest.fixture()
def sample_pyproject_path(tmp_path, sample_pyproject_content) -> str:
    """Write sample pyproject.toml to a temp file and return the path."""
    p = tmp_path / "pyproject.toml"
    p.write_text(sample_pyproject_content)
    return str(p)
