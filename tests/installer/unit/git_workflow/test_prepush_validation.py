"""
Unit tests for pre-push validation hook logic.

Tests the shell script logic without requiring actual git operations.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def test_repo():
    """Create temporary directory structure mimicking git repository."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        nwave_dir = repo_root / "nWave"
        nwave_dir.mkdir()

        # Initialize git repository
        subprocess.run(["git", "init"], cwd=repo_root, capture_output=True, check=True)

        # Get hook script path relative to project root
        project_root = Path(__file__).parent.parent.parent.parent.parent
        hook_script = project_root / "scripts" / "hooks" / "pre-push"

        yield {
            "repo_root": repo_root,
            "nwave_dir": nwave_dir,
            "hook_script": hook_script,
        }


def run_hook(hook_script: Path, cwd: Path, env: dict) -> subprocess.CompletedProcess:
    """
    Run hook script cross-platform.

    On Windows, shebangs are not honored by subprocess.run(), so we must
    explicitly invoke Python to run the script. This mirrors how git
    handles hooks via Git Bash.

    Args:
        hook_script: Path to the hook script
        cwd: Working directory for execution
        env: Environment variables to add (merged with system env)

    Returns:
        CompletedProcess with stdout, stderr, and returncode
    """
    # Merge with system environment to preserve PATH (needed for git)
    full_env = os.environ.copy()
    full_env.update(env)

    return subprocess.run(
        [sys.executable, str(hook_script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=full_env,
    )


class TestPrePushValidation:
    """Unit tests for pre-push hook validation logic."""

    def test_passes_when_version_and_releaserc_exist(self, test_repo):
        """Pre-push validation succeeds when all required files exist."""
        # Arrange
        version_file = test_repo["nwave_dir"] / "VERSION"
        version_file.write_text("1.5.7\n")

        releaserc = test_repo["repo_root"] / ".releaserc"
        releaserc.write_text('{"branches": ["main"]}')

        # Act
        result = run_hook(
            test_repo["hook_script"],
            test_repo["repo_root"],
            {"GIT_DIR": str(test_repo["repo_root"] / ".git")},
        )

        # Assert
        assert result.returncode == 0, f"Hook failed unexpectedly:\n{result.stderr}"
        assert "VERSION file missing" not in result.stderr
        assert "semantic-release not configured" not in result.stderr

    def test_fails_when_version_file_missing(self, test_repo):
        """Pre-push validation fails when VERSION file is missing."""
        # Arrange
        releaserc = test_repo["repo_root"] / ".releaserc"
        releaserc.write_text('{"branches": ["main"]}')

        # Act
        result = run_hook(
            test_repo["hook_script"],
            test_repo["repo_root"],
            {"GIT_DIR": str(test_repo["repo_root"] / ".git")},
        )

        # Assert
        assert result.returncode == 1, "Hook should have failed"
        output = result.stdout + result.stderr
        assert "VERSION file missing" in output
        assert "Create nWave/VERSION with current version (e.g., '1.5.7')" in output

    def test_fails_when_releaserc_missing(self, test_repo):
        """Pre-push validation fails when semantic-release config is missing."""
        # Arrange
        version_file = test_repo["nwave_dir"] / "VERSION"
        version_file.write_text("1.5.7\n")

        # Act
        result = run_hook(
            test_repo["hook_script"],
            test_repo["repo_root"],
            {"GIT_DIR": str(test_repo["repo_root"] / ".git")},
        )

        # Assert
        assert result.returncode == 1, "Hook should have failed"
        output = result.stdout + result.stderr
        assert "semantic-release not configured" in output
        assert "Run 'npx semantic-release-cli setup'" in output

    def test_accepts_release_config_js_alternative(self, test_repo):
        """Pre-push validation accepts release.config.js as alternative to .releaserc."""
        # Arrange
        version_file = test_repo["nwave_dir"] / "VERSION"
        version_file.write_text("1.5.7\n")

        release_config = test_repo["repo_root"] / "release.config.js"
        release_config.write_text("module.exports = { branches: ['main'] };")

        # Act
        result = run_hook(
            test_repo["hook_script"],
            test_repo["repo_root"],
            {"GIT_DIR": str(test_repo["repo_root"] / ".git")},
        )

        # Assert
        output = result.stdout + result.stderr
        assert result.returncode == 0, f"Hook failed unexpectedly:\n{output}"
        assert "semantic-release not configured" not in output
