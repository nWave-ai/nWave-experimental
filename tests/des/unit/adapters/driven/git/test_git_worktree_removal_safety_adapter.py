"""Unit tests for GitWorktreeRemovalSafetyAdapter's degrade-LOUD contract.

Mirrors `test_git_commit_tree_path_adapter.py`'s shape: mocked-`subprocess.run`
edge cases for the degrade paths, plus real-git end-to-end tests (a real
repo + a real linked worktree) so the mocked porcelain-parsing cases can't
silently drift from real `git worktree list --porcelain` output.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from des.adapters.driven.git.git_worktree_removal_safety_adapter import (
    GitWorktreeRemovalSafetyAdapter,
)
from des.ports.driven_ports.worktree_removal_safety_port import Indeterminate


def test_git_binary_missing_degrades_to_indeterminate() -> None:
    adapter = GitWorktreeRemovalSafetyAdapter()
    with patch("subprocess.run", side_effect=FileNotFoundError("no git")):
        result = adapter.is_locked(Path("/repo"), Path("/repo-wt"))
    assert isinstance(result, Indeterminate)
    assert "git" in result.reason.lower()


def test_worktree_list_failure_degrades_to_indeterminate() -> None:
    adapter = GitWorktreeRemovalSafetyAdapter()
    failed = MagicMock(
        returncode=128, stdout="", stderr="fatal: not a git repository\n"
    )
    with patch("subprocess.run", return_value=failed):
        result = adapter.is_locked(Path("/not-a-repo"), Path("/wt"))
    assert isinstance(result, Indeterminate)


def test_unregistered_worktree_degrades_to_indeterminate() -> None:
    adapter = GitWorktreeRemovalSafetyAdapter()
    listing = MagicMock(
        returncode=0,
        stdout="worktree /repo\nHEAD abc123\nbranch refs/heads/main\n\n",
        stderr="",
    )
    with patch("subprocess.run", return_value=listing):
        result = adapter.is_locked(Path("/repo"), Path("/not-registered"))
    assert isinstance(result, Indeterminate)
    assert "not a registered worktree" in result.reason


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "t@example.com"], cwd=path, check=True
    )
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    (path / "seed.txt").write_text("seed", encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", "seed")


def test_real_repo_lock_and_unlock_end_to_end(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-b", "lane", str(wt), "HEAD")

    adapter = GitWorktreeRemovalSafetyAdapter()
    assert adapter.is_locked(repo, wt) is False

    _git(repo, "worktree", "lock", str(wt))
    assert adapter.is_locked(repo, wt) is True

    _git(repo, "worktree", "unlock", str(wt))
    assert adapter.is_locked(repo, wt) is False


def test_real_repo_unmerged_commits_named(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-b", "lane", str(wt), "HEAD")

    (wt / "wip.txt").write_text("wip", encoding="utf-8")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-q", "-m", "lane wip commit")

    adapter = GitWorktreeRemovalSafetyAdapter()
    result = adapter.has_unmerged_commits(repo, wt, "master")
    assert result != ()
    assert not isinstance(result, Indeterminate)
    assert any("lane wip commit" in subject for subject in result)


def test_real_repo_proper_ancestor_with_zero_commits_ahead_is_indeterminate(
    tmp_path: Path,
) -> None:
    """The fabricated-commit-count bugfix's own regression case: a worktree
    branched from trunk's tip with ZERO commits of its own, left behind
    while trunk advances past it via unrelated work. `is_merged_contribution`
    conservatively refuses (it is a proper ancestor, not the tip -- see its
    own docstring case 2), and `target..head` is genuinely empty. The old
    code synthesized a one-element tuple holding an explanation STRING and
    the caller counted it as "1 commit(s)" -- a number nobody measured
    (`git log --oneline master..lane` on this exact fixture returns nothing).
    The fix must report `Indeterminate` naming the real uncertainty, never a
    non-empty tuple.

    UNCHANGED by the content-not-sha integration-check fix (K4 matrix):
    that fix only ever applies when `head_sha` is NOT an ancestor of
    `target_branch` at all (the cherry-pick case) -- `lane` here IS an
    ancestor, so this row4-incident protection still gates it exactly as
    before.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-b", "lane", str(wt), "HEAD")
    # `lane` makes NO commits of its own. `master` advances past it.
    (repo / "trunk-moved-on.txt").write_text("trunk work", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "trunk advances past lane")

    # Ground truth this test protects: genuinely zero commits ahead.
    log_ahead = _git(wt, "log", "--oneline", "master..lane")
    assert log_ahead == ""

    adapter = GitWorktreeRemovalSafetyAdapter()
    result = adapter.has_unmerged_commits(repo, wt, "master")

    assert isinstance(result, Indeterminate)
    assert "unknown" in result.reason
    assert "1 commit" not in result.reason
    assert "unmerged into" not in result.reason


def test_real_repo_merged_branch_is_empty_tuple(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-b", "lane", str(wt), "HEAD")

    (wt / "wip.txt").write_text("wip", encoding="utf-8")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-q", "-m", "lane wip commit")

    _git(repo, "merge", "-q", "--no-edit", "lane")

    adapter = GitWorktreeRemovalSafetyAdapter()
    result = adapter.has_unmerged_commits(repo, wt, "master")
    assert result == ()


def test_dirty_state_unregistered_worktree_degrades_to_indeterminate() -> None:
    adapter = GitWorktreeRemovalSafetyAdapter()
    listing = MagicMock(
        returncode=0,
        stdout="worktree /repo\nHEAD abc123\nbranch refs/heads/main\n\n",
        stderr="",
    )
    with patch("subprocess.run", return_value=listing):
        result = adapter.has_dirty_state(Path("/repo"), Path("/not-registered"))
    assert isinstance(result, Indeterminate)
    assert "dirty-state" in result.reason


def test_dirty_state_git_status_failure_degrades_to_indeterminate(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-b", "lane", str(wt), "HEAD")

    class _RaisingGitWorktreePort:
        def has_uncommitted_changes(self, repo: Path, path: Path) -> bool:
            raise subprocess.CalledProcessError(128, ["git", "status"], stderr="boom")

    adapter = GitWorktreeRemovalSafetyAdapter(
        git_worktree_port=_RaisingGitWorktreePort()
    )
    result = adapter.has_dirty_state(repo, wt)
    assert isinstance(result, Indeterminate)


def test_real_repo_clean_worktree_is_not_dirty(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-b", "lane", str(wt), "HEAD")

    adapter = GitWorktreeRemovalSafetyAdapter()
    assert adapter.has_dirty_state(repo, wt) is False


def test_real_repo_uncommitted_change_is_dirty_even_when_branch_is_merged(
    tmp_path: Path,
) -> None:
    """The distinguishing case: a fully-merged branch (no unmerged COMMITS)
    can still carry uncommitted work -- dirty-state is its OWN evidence
    category, checked independently of unmerged-commits."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-b", "lane", str(wt), "HEAD")

    (wt / "untracked.txt").write_text("uncommitted", encoding="utf-8")

    adapter = GitWorktreeRemovalSafetyAdapter()
    assert adapter.has_dirty_state(repo, wt) is True
    assert adapter.has_unmerged_commits(repo, wt, "master") == ()


def test_real_repo_cherry_picked_lane_commit_reports_integrated(
    tmp_path: Path,
) -> None:
    """K4 matrix: our whole integration model is cherry-pick onto trunk, so
    every clean, fully integrated lane's own commits carry a BRAND NEW sha
    on trunk -- sha ancestry alone (`is_ancestor`) is FALSE for every one
    of them, wrongly refusing a lane that has nothing left unintegrated.
    `has_unmerged_commits` must judge by CONTENT (`git cherry`'s own
    patch-id comparison) and report the lane as fully integrated (empty
    tuple), not merely "not an ancestor"."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-b", "lane", str(wt), "HEAD")

    (wt / "feature.txt").write_text("lane work\n", encoding="utf-8")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-q", "-m", "add feature (unique content)")
    lane_sha = _git(wt, "rev-parse", "HEAD").strip()

    # Trunk advances FIRST, on unrelated work -- guarantees the cherry-pick
    # below lands on a DIFFERENT parent than `lane`'s own commit had, so
    # the resulting commit object is guaranteed a genuinely different sha
    # (never relying on same-second timestamp coincidence for that).
    (repo / "trunk-only.txt").write_text("trunk work\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "unrelated trunk work")

    # Integrate the SAME content onto trunk via cherry-pick -- a brand new
    # sha for identical content, never an ancestor of `lane`'s commit or
    # vice versa.
    _git(repo, "cherry-pick", lane_sha)
    trunk_sha = _git(repo, "rev-parse", "HEAD").strip()
    assert trunk_sha != lane_sha, "test setup invalid: cherry-pick must mint a new sha"

    adapter = GitWorktreeRemovalSafetyAdapter()
    result = adapter.has_unmerged_commits(repo, wt, "master")

    assert result == (), (
        f"a cherry-picked lane commit must read as integrated by content, "
        f"got {result!r}"
    )


def test_real_repo_truly_unique_commit_is_still_refused(tmp_path: Path) -> None:
    """The negative control for the fix above: a lane commit that was
    NEVER integrated anywhere on trunk -- by sha or by content -- must
    still be named unmerged, proving the content check genuinely
    discriminates rather than passing unconditionally."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-b", "lane", str(wt), "HEAD")

    (wt / "unintegrated.txt").write_text("never landed anywhere\n", encoding="utf-8")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-q", "-m", "truly unique lane commit")

    # Trunk advances via UNRELATED work -- never touching the lane's content.
    (repo / "trunk-only.txt").write_text("trunk work\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "unrelated trunk work")

    adapter = GitWorktreeRemovalSafetyAdapter()
    result = adapter.has_unmerged_commits(repo, wt, "master")

    assert result != ()
    assert not isinstance(result, Indeterminate)
    assert any("truly unique lane commit" in subject for subject in result)
