"""`HeadAdvance` is the one owner of moving a destination's HEAD forward.

Both callers -- the delivery runner's integration and the `des lane integrate`
step -- reach the destination through this object, so the case neither of them
ever meets in a green run (the destination having moved) is implemented once and
pinned here rather than twice and pinned nowhere.

The two enactments are exercised on REAL repositories, because what separates
them is what Git actually does to a working tree, which a double cannot show.
The non-answer branches use a substituted observer, because an absent Git cannot
be produced on a box that has one.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from des.adapters.driven.git.git_observation import GitObservation, GitUnanswered
from des.application.head_advance import AdvanceRefusal, HeadAdvance


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, text=True, capture_output=True
    ).stdout.strip()


def commit(root: Path, name: str, text: str) -> str:
    (root / name).write_text(text)
    git(root, "add", ".")
    git(root, "commit", "-qm", name)
    return git(root, "rev-parse", "HEAD")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    repository = tmp_path / "root"
    repository.mkdir()
    git(repository, "init", "-q")
    git(repository, "config", "user.email", "a@b")
    git(repository, "config", "user.name", "a")
    commit(repository, "README.md", "x\n")
    return repository


def unanswered(*_args: object, **_kwargs: object) -> GitObservation:
    """An observation of a Git that never ran -- the seam's own non-answer shape."""
    reason = GitUnanswered("GitUnanswered", "git could not be executed", "install git")
    return GitObservation(127, "", reason.why, reason)


class TestTheCompareAndSwapWritesOnlyOntoWhatItLastObserved:
    def test_it_writes_when_the_destination_is_still_expected_old(self, root):
        base = git(root, "rev-parse", "HEAD")
        candidate = git(root, "commit-tree", f"{base}^{{tree}}", "-p", base, "-m", "c")

        assert HeadAdvance().swap(root, candidate, base) is None
        assert git(root, "rev-parse", "HEAD") == candidate

    def test_it_refuses_a_moved_destination_without_writing(self, root):
        stale = git(root, "rev-parse", "HEAD")
        moved = commit(root, "other.md", "y\n")
        candidate = git(
            root, "commit-tree", f"{stale}^{{tree}}", "-p", stale, "-m", "c"
        )

        refused = HeadAdvance().swap(root, candidate, stale)

        assert isinstance(refused, AdvanceRefusal)
        assert refused.what == "IntegrationStale"
        assert refused.unanswered is None
        assert git(root, "rev-parse", "HEAD") == moved

    def test_a_git_that_never_answered_is_not_reported_as_a_moved_destination(
        self, root
    ):
        refused = HeadAdvance(unanswered).swap(root, "aaa", "bbb")

        assert isinstance(refused, AdvanceRefusal)
        # The DISCRIMINANT the caller needs: nothing about the repository was
        # observed, so no caller may turn this into a repository fact.
        assert refused.unanswered is not None
        assert refused.what == "GitUnavailable"


class TestTheFastForwardAdvancesAWholeCheckout:
    def test_it_moves_the_files_and_reports_what_it_advanced_from(self, root, tmp_path):
        base = git(root, "rev-parse", "HEAD")
        lane = tmp_path / "lane"
        git(root, "worktree", "add", "-q", str(lane), "-b", "lane/probe", base)
        tip = commit(lane, "added.md", "new\n")

        advanced = HeadAdvance().fast_forward(root, tip)

        assert advanced == base
        assert git(root, "rev-parse", "HEAD") == tip
        # A bare `update-ref` would have left this file absent while the ref
        # named a commit that carries it -- the silent-wrong this form exists
        # to avoid on a live checkout.
        assert (root / "added.md").read_text() == "new\n"
        assert git(root, "status", "--porcelain") == ""

    def test_it_refuses_when_the_destination_is_not_an_ancestor(self, root, tmp_path):
        base = git(root, "rev-parse", "HEAD")
        lane = tmp_path / "lane"
        git(root, "worktree", "add", "-q", str(lane), "-b", "lane/probe", base)
        tip = commit(lane, "added.md", "new\n")
        moved = commit(root, "elsewhere.md", "z\n")

        refused = HeadAdvance().fast_forward(root, tip)

        assert isinstance(refused, AdvanceRefusal)
        assert refused.what == "IntegrationStale"
        assert moved in refused.why and tip in refused.why
        assert git(root, "rev-parse", "HEAD") == moved

    def test_a_failing_ancestry_query_is_not_read_as_a_negative_answer(self, root):
        """Exit 1 ANSWERS the question; any other status is the tool failing.

        Collapsing the two would report a broken Git as a moved destination,
        sending the caller to rebase a branch nothing was ever measured about.
        """

        def broken(observed_root: Path, *args: str, **kwargs: object) -> GitObservation:
            if args[:2] == ("merge-base", "--is-ancestor"):
                return GitObservation(128, "", "fatal: bad object")
            return HeadAdvance().observe(observed_root, *args, **kwargs)

        refused = HeadAdvance(broken).fast_forward(root, "deadbeef")

        assert isinstance(refused, AdvanceRefusal)
        assert refused.what == "GitUnavailable"

    def test_it_refuses_rather_than_overwriting_uncommitted_work(self, root, tmp_path):
        base = git(root, "rev-parse", "HEAD")
        lane = tmp_path / "lane"
        git(root, "worktree", "add", "-q", str(lane), "-b", "lane/probe", base)
        tip = commit(lane, "README.md", "from the lane\n")
        (root / "README.md").write_text("uncommitted local edit\n")

        refused = HeadAdvance().fast_forward(root, tip)

        assert isinstance(refused, AdvanceRefusal)
        assert refused.what == "FastForwardRefused"
        assert git(root, "rev-parse", "HEAD") == base
        assert (root / "README.md").read_text() == "uncommitted local edit\n"
