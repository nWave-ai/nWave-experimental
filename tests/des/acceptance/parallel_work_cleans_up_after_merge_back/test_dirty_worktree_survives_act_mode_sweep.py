"""Regression: a worktree with real UNCOMMITTED work is never swept, against
REAL git (not the pure classifier / FakeGitWorktree double).

Defect (defects.md: dirty-tree-worktree-guard-has-zero-real-git-coverage):
the dirty-tree guard that stops ``des verify-worktree-cleanup`` from removing
a worktree carrying real uncommitted work
(``GitWorktreeAdapter.has_uncommitted_changes``, wraps ``git status
--porcelain``) had ZERO coverage against real git -- only the pure
``classify_worktree_cleanup_state`` truth table (nude booleans) and an
in-memory ``FakeGitWorktree`` exercised it. The commit that introduced the
guard (e1e38fc7b) states the bug it closed was "observed three times ...
during development" -- an in-progress worktree force-removed, real data
loss. Its sibling regression for the OTHER false-positive class (non-
diverged ancestor) has a real-git test
(``test_nondiverged_ancestor_regression.py``, same directory); this was the
one asymmetric, unverified-against-reality guard.

Mirrors that sibling's shape exactly: build a real trunk repo + a real
linked worktree via the SHIPPED ``GitWorktreeAdapter`` (the same path
production uses), write untracked/modified content directly into the
worktree, run the REAL ``des verify-worktree-cleanup`` CLI in ACT mode
(never ``--check-only``), and assert the worktree SURVIVES with verdict
``HAS_UNCOMMITTED_CHANGES``. Must fail if the guard is ever removed or
bypassed -- that is the only way to know it protects rather than merely
appears to.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from des.adapters.driven.refactor.git_worktree_adapter import GitWorktreeAdapter
from des.cli import verify_worktree_cleanup


_TARGET_BRANCH = "trunk"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout


def _registered_worktrees(repo: Path) -> set[str]:
    out = _git(repo, "worktree", "list", "--porcelain")
    return {
        line[len("worktree ") :]
        for line in out.splitlines()
        if line.startswith("worktree ")
    }


def _last_json_line(stdout: str) -> dict:
    lines = [line for line in stdout.splitlines() if line.strip().startswith("{")]
    assert lines, f"no JSON report line in CLI stdout: {stdout!r}"
    return json.loads(lines[-1])


def _build_dirty_merged_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """A trunk repo + a linked worktree whose committed history is ALREADY
    merged onto trunk (so the merge-state check alone would say "safe to
    remove"), carrying real uncommitted work: one MODIFIED tracked file and
    one UNTRACKED file -- both must be enough to trip the guard.

    Returns ``(repo, worktree_path)``.
    """
    repo = tmp_path / "trunk-repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "regression@example.test")
    _git(repo, "config", "user.name", "Dirty Worktree Regression")
    (repo / "README.md").write_text("trunk seed\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "chore: seed trunk")
    _git(repo, "branch", "-m", _TARGET_BRANCH)

    worktree_path = tmp_path / "trunk-repo-dirty"
    GitWorktreeAdapter().create_worktree_from_tip(
        repo, "dirty-feature-plan", worktree_path
    )

    # Real, live edits AFTER the worktree was cut -- never committed.
    (worktree_path / "README.md").write_text(
        "trunk seed\nlive uncommitted edit\n", encoding="utf-8"
    )
    (worktree_path / "in-progress-note.md").write_text(
        "untracked work in flight\n", encoding="utf-8"
    )

    status = _git(worktree_path, "status", "--porcelain").strip()
    assert status, (
        "test setup invalid: the worktree must show real uncommitted changes "
        "for this regression to exercise the dirty-tree guard"
    )
    return repo, worktree_path


def test_dirty_worktree_survives_act_mode_sweep(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, worktree_path = _build_dirty_merged_worktree(tmp_path)
    before = _registered_worktrees(repo)
    assert str(worktree_path) in before

    # ACT mode (no --check-only): the destructive path the guard must block.
    exit_code = verify_worktree_cleanup.main(
        ["--repo", str(repo), "--target-branch", _TARGET_BRANCH]
    )
    payload = _last_json_line(capsys.readouterr().out)

    entry = next(e for e in payload["entries"] if e["path"] == str(worktree_path))
    assert entry["verdict"] == "HAS_UNCOMMITTED_CHANGES", (
        "a worktree carrying real uncommitted work (modified + untracked) "
        f"must never read as safe to remove. Got verdict={entry['verdict']!r}"
    )
    assert entry["removed"] is False
    assert exit_code == 0

    after = _registered_worktrees(repo)
    assert str(worktree_path) in after, (
        "DATA LOSS: a worktree holding real uncommitted work was force-removed "
        "by the ACT-mode sweep"
    )
    assert (worktree_path / "in-progress-note.md").exists(), (
        "DATA LOSS: the untracked in-progress file did not survive the sweep"
    )
