"""Integration tests for Commitizen (CZ) behavior assumptions.

We don't own CZ. These tests create real temporary git repos, configure
CZ, make conventional commits, and verify CZ returns what our pipeline
expects. If CZ changes behavior on upgrade, these tests catch it.

BDD scenario mapping:
  - Category 1 from test design: CZ commit analysis integration
  - Validates: feat→minor, fix→patch, docs→nothing, mixed→highest-wins
  - Guards: version maze from stale anchor (Test 1.5)
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest


if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Shared fixture: temporary git repo with CZ config
# ---------------------------------------------------------------------------

CZ_PYPROJECT = """\
[project]
name = "test-cz"
version = "{version}"

[tool.commitizen]
version = "{version}"
version_scheme = "pep440"
tag_format = "v$version"
name = "cz_conventional_commits"
"""


@pytest.fixture()
def cz_repo(tmp_path):
    """Create a temporary git repo with CZ config and an initial tagged commit.

    Returns a helper object with .path, .commit(), and .cz_get_next() methods.
    """
    return CZRepo.create(tmp_path, initial_version="1.2.0")


class CZRepo:
    """Helper to manage a temporary git repo for CZ integration tests."""

    def __init__(self, path: Path, version: str):
        self.path = path
        self.version = version

    @classmethod
    def create(cls, tmp_path: Path, initial_version: str = "1.2.0") -> CZRepo:
        repo = cls(tmp_path, initial_version)
        repo._git("init", "-b", "main")
        repo._git("config", "user.email", "test@example.com")
        repo._git("config", "user.name", "Test")

        # Write CZ-configured pyproject.toml
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(CZ_PYPROJECT.format(version=initial_version))

        # Initial commit + tag
        repo._git("add", ".")
        repo._git("commit", "-m", f"chore: initial release {initial_version}")
        repo._git("tag", f"v{initial_version}")

        return repo

    def commit(self, message: str, filename: str | None = None) -> None:
        """Create a file and commit with the given conventional commit message."""
        if filename is None:
            # Generate unique filename from message
            filename = message.replace(" ", "_").replace(":", "")[:40] + ".txt"
        (self.path / filename).write_text(message)
        self._git("add", ".")
        self._git("commit", "-m", message)

    def cz_get_next(self) -> str | None:
        """Run `cz bump --get-next` and return the version string, or None if no bump."""
        result = subprocess.run(
            [sys.executable, "-m", "commitizen.cli", "bump", "--get-next"],
            capture_output=True,
            text=True,
            cwd=str(self.path),
            env={**os.environ, "CZ_ROOT": str(self.path)},
        )
        if result.returncode != 0:
            return None
        # CZ outputs the next version on stdout
        return result.stdout.strip()

    def _git(self, *args: str) -> subprocess.CompletedProcess:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            cwd=str(self.path),
        )
        if result.returncode != 0:
            msg = f"git {' '.join(args)} failed: {result.stderr}"
            raise RuntimeError(msg)
        return result


# ---------------------------------------------------------------------------
# Test 1.1: CZ returns minor for feat commits
# ---------------------------------------------------------------------------


class TestCZCommitAnalysis:
    """Verify CZ returns expected bump levels for conventional commit types."""

    def test_cz_returns_minor_for_feat_commit(self, cz_repo):
        """Given a repo tagged at v1.2.0,
        and a commit "feat(agents): add skill activation audit",
        when CZ analyzes commits,
        then CZ returns "1.3.0" (minor bump)."""
        cz_repo.commit("feat(agents): add skill activation audit")

        result = cz_repo.cz_get_next()

        assert result == "1.3.0", f"Expected 1.3.0 (minor), got {result}"

    def test_cz_returns_patch_for_fix_commit(self, cz_repo):
        """Given a repo tagged at v1.2.0,
        and a commit "fix(release): correct version sync",
        when CZ analyzes commits,
        then CZ returns "1.2.1" (patch bump)."""
        cz_repo.commit("fix(release): correct version sync")

        result = cz_repo.cz_get_next()

        assert result == "1.2.1", f"Expected 1.2.1 (patch), got {result}"

    def test_cz_returns_nothing_for_docs_only(self, cz_repo):
        """Given a repo tagged at v1.2.0,
        and a commit "docs: update discord URL",
        when CZ analyzes commits,
        then CZ returns nothing (no bump needed).

        This is the trigger for our pipeline's fallback path."""
        cz_repo.commit("docs: update discord URL")

        result = cz_repo.cz_get_next()

        assert result is None, (
            f"CZ returned '{result}' for docs-only commit; "
            "expected nothing (our fallback depends on this)"
        )

    def test_cz_highest_bump_wins_with_mixed_commits(self, cz_repo):
        """Given a repo tagged at v1.2.0 with mixed commits:
          docs: update discord URL
          feat(agents): skill activation audit
          fix(release): use promotion chain version
          fix(release): sync commitizen anchors
        when CZ analyzes ALL commits,
        then CZ returns "1.3.0" (feat wins over fix; docs ignored).

        This is today's exact scenario from the git log."""
        cz_repo.commit("docs: update discord URL", "discord.md")
        cz_repo.commit("feat(agents): skill activation audit", "audit.py")
        cz_repo.commit("fix(release): use promotion chain version", "chain.py")
        cz_repo.commit("fix(release): sync commitizen anchors", "sync.py")

        result = cz_repo.cz_get_next()

        assert result == "1.3.0", (
            f"Expected 1.3.0 (feat wins), got {result}. "
            "CZ must pick the highest bump across all commits"
        )


# ---------------------------------------------------------------------------
# Test 1.5: CZ anchor determines commit scan range (VERSION MAZE)
# ---------------------------------------------------------------------------


class TestCZAnchorScanRange:
    """The CZ anchor (tool.commitizen.version) determines which commits are scanned.

    A stale anchor causes CZ to recalculate an already-released version.
    This IS the version maze bug."""

    def test_correct_anchor_produces_next_version(self, tmp_path):
        """Given v1.2.0 is released (tag exists, anchor=1.2.0),
        and a new feat commit after v1.2.0,
        when CZ analyzes with correct anchor,
        then CZ returns "1.3.0" (scans only post-1.2.0 commits)."""
        repo = CZRepo.create(tmp_path, initial_version="1.2.0")
        repo.commit("feat(x): new feature after stable")

        result = repo.cz_get_next()

        assert result == "1.3.0", (
            f"With correct anchor 1.2.0, expected 1.3.0, got {result}"
        )

    def test_stale_anchor_reproduces_version_maze(self, tmp_path):
        """Given:
          - v1.1.28 tag on commit A (old stable)
          - feat commits between A and B
          - v1.2.0 tag on commit B (new stable)
          - BUT tool.commitizen.version still says "1.1.28" (STALE!)
          - new feat commit C after B
        when CZ analyzes with stale anchor,
        then CZ returns "1.2.0" (not 1.3.0!), because it scans from 1.1.28.

        THIS IS THE VERSION MAZE: 1.2.0 is already released but CZ
        thinks it's the next version because the anchor is wrong."""
        # Build repo at v1.1.28
        repo = CZRepo.create(tmp_path, initial_version="1.1.28")

        # Feat commits that led to v1.2.0 stable
        repo.commit("feat(release): migrate to CZ commands", "migrate.py")
        repo.commit("feat(release): expand CZ config", "config.py")

        # Simulate stable release: tag v1.2.0 BUT don't update CZ anchor
        repo._git("tag", "v1.2.0")

        # New commit after v1.2.0 (this is the next dev cycle)
        repo.commit("feat(agents): skill activation audit", "audit.py")

        # CZ still thinks anchor is 1.1.28 (stale!)
        result = repo.cz_get_next()

        # CZ scans from v1.1.28: sees feat → minor → 1.2.0
        # But 1.2.0 is already released! This is the maze.
        assert result == "1.2.0", (
            f"With stale anchor 1.1.28, expected CZ to return 1.2.0 "
            f"(the maze version), got {result}"
        )
