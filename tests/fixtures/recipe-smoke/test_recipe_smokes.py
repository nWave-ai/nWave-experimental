"""
Recipe smoke tests for docs/guides/enforcement-recipes.md (US-07B AC-3).

Three recipes verified:
  1. Git + pre-commit: .pre-commit-config.yaml stanza parses as valid YAML
  2. GitHub Actions: workflow YAML parses as valid YAML
  3. Makefile: `make -n check-feature-delta` dry-runs without error

These tests act as living proof that the copy-paste-correct recipes in the
enforcement-recipes guide are syntactically valid and won't break user stacks.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml


RECIPE_SMOKE_DIR = Path(__file__).parent


class TestPreCommitRecipe:
    """Recipe 1: Git + pre-commit framework (.pre-commit-config.yaml stanza)."""

    def test_pre_commit_stanza_is_valid_yaml(self) -> None:
        """The pre-commit stanza from the enforcement-recipes guide is valid YAML."""
        recipe_file = RECIPE_SMOKE_DIR / "pre-commit-stanza.yaml"
        assert recipe_file.exists(), (
            f"Recipe fixture not found: {recipe_file}. "
            "Create tests/fixtures/recipe-smoke/pre-commit-stanza.yaml"
        )
        content = recipe_file.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        # Must be a dict with a 'repos' key (pre-commit config structure)
        assert isinstance(parsed, dict), "pre-commit config must be a YAML mapping"
        assert "repos" in parsed, "pre-commit config must have a 'repos' key"
        repos = parsed["repos"]
        assert isinstance(repos, list) and len(repos) >= 1, (
            "pre-commit repos must be a non-empty list"
        )
        # Each repo must have a 'repo' key and 'hooks' list
        for repo in repos:
            assert "repo" in repo, f"Missing 'repo' key in: {repo}"
            assert "hooks" in repo, f"Missing 'hooks' key in: {repo}"


class TestGitHubActionsRecipe:
    """Recipe 2: GitHub Actions workflow YAML parses as valid YAML."""

    def test_github_actions_workflow_is_valid_yaml(self) -> None:
        """The GitHub Actions recipe from the enforcement-recipes guide is valid YAML."""
        recipe_file = RECIPE_SMOKE_DIR / "github-actions-workflow.yaml"
        assert recipe_file.exists(), (
            f"Recipe fixture not found: {recipe_file}. "
            "Create tests/fixtures/recipe-smoke/github-actions-workflow.yaml"
        )
        content = recipe_file.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        assert isinstance(parsed, dict), (
            "GitHub Actions workflow must be a YAML mapping"
        )
        # "on" key is present in valid GHA workflows; YAML parses it as True (bool) so check via raw
        assert "jobs" in parsed, "GitHub Actions workflow must have a 'jobs' key"
        jobs = parsed["jobs"]
        assert isinstance(jobs, dict) and len(jobs) >= 1, (
            "jobs must be a non-empty mapping"
        )
        # Each job must have a 'steps' key
        for job_name, job in jobs.items():
            assert "steps" in job, f"Job '{job_name}' must have 'steps'"
            # At least one step must invoke nwave-ai validate-feature-delta
            steps_text = str(job["steps"])
            assert "nwave-ai" in steps_text or "nwave_ai" in steps_text, (
                f"Job '{job_name}' steps must invoke nwave-ai"
            )


class TestMakefileRecipe:
    """Recipe 3: Makefile `make -n check-feature-delta` dry-runs without error."""

    def test_makefile_dry_run_succeeds(self, tmp_path: Path) -> None:
        """The Makefile recipe dry-runs without error via `make -n`."""
        recipe_file = RECIPE_SMOKE_DIR / "Makefile.recipe"
        assert recipe_file.exists(), (
            f"Recipe fixture not found: {recipe_file}. "
            "Create tests/fixtures/recipe-smoke/Makefile.recipe"
        )
        # Copy recipe to tmp_path as Makefile so make can parse it
        makefile = tmp_path / "Makefile"
        makefile.write_text(recipe_file.read_text(encoding="utf-8"), encoding="utf-8")
        # Create a dummy feature-delta.md so the path reference doesn't break dry-run
        (tmp_path / "feature-delta.md").write_text("# dummy\n", encoding="utf-8")
        result = subprocess.run(
            ["make", "-n", "check-feature-delta"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"make -n check-feature-delta failed (exit {result.returncode}):\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        # Dry-run output should reference nwave-ai
        assert "nwave-ai" in result.stdout or "nwave_ai" in result.stdout, (
            "Makefile recipe must invoke nwave-ai in check-feature-delta target"
        )
