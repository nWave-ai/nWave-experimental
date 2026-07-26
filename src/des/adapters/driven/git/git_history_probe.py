"""GitHistoryProbe -- re-verifies a committed step's SHA against git history.

Feature `classic-spine-decommission`, slice-06 (M2). A classic feature's
`execution-log.json` records a `COMMIT/PASS` event per delivered step. That
event is a CLAIM, not proof: the commit may have been reverted, may not exist
in this clone's history at all, or may have been green only repo-side and red
now. The conversion planner therefore NEVER trusts the logged `sha_verdict` --
it asks `GitHistoryProbe` to re-verify the SHA against the real repository.

Extension Justification (nw-quality-framework / Mandate against Parallel
Implementations):

  WHY-NEW-FILE: src/des/adapters/driven/git/git_history_probe.py
    CLOSEST-EXISTING: src/des/adapters/driven/git/git_commit_verifier.py
    EXTENSION-COST: GitCommitVerifier implements the `CommitVerifier` port
      whose contract is "find a commit by Step-Id trailer"
      (`verify_commit -> CommitVerificationResult`). Adding SHA
      re-verification would force a second unrelated method onto a
      single-responsibility port and a result shape (`verified: bool`) that
      cannot express the four-way `ShaVerdict`.
    PARALLEL-RATIONALE: GitHistoryProbe answers a different question --
      re-verify a *known* SHA's reachability and test-state, returning a
      `ShaVerdict` -- a distinct port contract the DESIGN Reuse Analysis
      explicitly records as a NEW thin REUSE adapter.

This is a thin REUSE adapter over `git cat-file` / `git merge-base` plus a
test-state read. `verify_sha` is pure-read: it queries, never mutates.
"""

from __future__ import annotations

import subprocess
from enum import Enum
from typing import TYPE_CHECKING

from des.adapters.driven.git.git_constants import GIT_HEAD


if TYPE_CHECKING:
    from pathlib import Path


# The file a delivered step's commit carries in its tree recording whether the
# step's tests were green at that SHA. Re-verification reads it out of the
# committed tree (`git cat-file blob {sha}:{path}`) -- a genuine git-history
# query against committed content, never a roadmap-trusted claim.
TEST_STATE_PATH = ".nwave/step-test-state"


class ShaVerdict(str, Enum):
    """The outcome of one M2 commit-SHA re-verification.

    GREEN     -- SHA exists, reachable from HEAD, tests green at that SHA now.
    REVERTED  -- SHA exists but is not reachable from HEAD (commit reverted).
    ABSENT    -- SHA does not exist in git history.
    TESTS_RED -- SHA exists and is reachable, but its tests are red now.
    """

    GREEN = "green"
    REVERTED = "reverted"
    ABSENT = "absent"
    TESTS_RED = "tests_red"


class GitHistoryProbe:
    """Re-verifies committed-step SHAs against a real git repository.

    Constructed over a repository root; `verify_sha` runs read-only git
    subprocesses inside it. The probe never mutates the repository.
    """

    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root

    def verify_sha(self, sha: str) -> ShaVerdict:
        """Re-verify one committed-step SHA against git history.

        Returns `ABSENT` when the SHA is unknown to this repository,
        `REVERTED` when it exists but is unreachable from HEAD, `TESTS_RED`
        when it is reachable but its recorded test-state is red, and `GREEN`
        only when the SHA is reachable with green tests.
        """
        if not self._sha_exists(sha):
            return ShaVerdict.ABSENT
        if not self._sha_reachable(sha):
            return ShaVerdict.REVERTED
        if not self._tests_green_at(sha):
            return ShaVerdict.TESTS_RED
        return ShaVerdict.GREEN

    def _sha_exists(self, sha: str) -> bool:
        """Whether `sha` resolves to a commit object in this repository."""
        return self._git("cat-file", "-e", f"{sha}^{{commit}}").returncode == 0

    def _sha_reachable(self, sha: str) -> bool:
        """Whether `sha` is an ancestor of HEAD (i.e. not reverted away)."""
        return self._git("merge-base", "--is-ancestor", sha, GIT_HEAD).returncode == 0

    def _tests_green_at(self, sha: str) -> bool:
        """Whether the step's tests were green at `sha`.

        Reads the `TEST_STATE_PATH` blob out of the committed tree. A commit
        with no recorded test-state is treated as green -- the test-state file
        is the explicit red marker, its absence is not a failure signal.
        """
        completed = self._git("cat-file", "blob", f"{sha}:{TEST_STATE_PATH}")
        if completed.returncode != 0:
            return True
        return completed.stdout.strip() != "red"

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        """Run a read-only git subprocess inside the repository root."""
        return subprocess.run(
            ["git", "-C", str(self._repo_root), *args],
            capture_output=True,
            text=True,
        )
