"""Regression: a non-diverged worktree is NOT swept just because trunk moved past it.

Data-loss bug (row4 incident, 2026-07-20): ``WorktreeCleanupService`` classified a
worktree as ``CLEANUP_DUE`` using ONLY ``is_ancestor(head_sha, target_branch)``.
That predicate is TRUE in two very different situations:

1. the worktree's OWN commits genuinely merged onto trunk (the safe case), and
2. the worktree made ZERO commits of its own and trunk merely advanced PAST the
   commit the worktree was cut from, on trunk's own mainline, via unrelated work
   (the DESTRUCTIVE false-positive).

Concretely: a worktree cut at commit ``C`` (no commits of its own), then an
unrelated bugfix lands on trunk as ``C'`` whose parent IS ``C``. Now
``is_ancestor(C, trunk@C')`` is TRUE even though the worktree merged nothing --
so an ACT-mode sweep force-removed the live, in-progress worktree (losing any
uncommitted work in it).

This drives the REAL production ``des verify-worktree-cleanup`` CLI in ACT mode
(never ``--check-only``) against exactly that state and asserts the worktree
SURVIVES and is reported ``NOT_YET_MERGEABLE`` -- nothing of its own could have
merged. Substrate is built through the SHIPPED ``GitWorktreeAdapter`` (the same
worktree-lifecycle path production uses), so the "ancestor but not merged"
precondition is genuinely git-state-true, never fixture fiat.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from des.adapters.driven.git.git_subprocess import is_ancestor
from des.adapters.driven.refactor.git_worktree_adapter import GitWorktreeAdapter
from des.cli import verify_worktree_cleanup


_TARGET_BRANCH = "trunk"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout


def _build_nondiverged_state(tmp_path: Path) -> tuple[Path, Path]:
    """A trunk repo + one linked worktree cut from trunk's tip that makes ZERO
    commits of its own, after which trunk advances one unrelated commit (so the
    worktree's HEAD becomes a proper ancestor of trunk on trunk's mainline).

    Returns ``(repo, worktree_path)``.
    """
    repo = tmp_path / "trunk-repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "regression@example.test")
    _git(repo, "config", "user.name", "Non-diverged Regression")
    (repo / "README.md").write_text("trunk seed\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "chore: seed trunk")
    _git(repo, "branch", "-m", _TARGET_BRANCH)

    # Worktree cut from trunk's tip -- makes NO commit of its own (mid-work).
    worktree_path = tmp_path / "trunk-repo-row4"
    handle = GitWorktreeAdapter().create_worktree_from_tip(
        repo, "row4-feature-plan", worktree_path
    )

    # Unrelated bugfix lands on trunk; its parent IS the worktree's HEAD.
    (repo / "fix.py").write_text("unrelated fix\n", encoding="utf-8")
    _git(repo, "add", "fix.py")
    _git(repo, "commit", "-q", "-m", "fix: unrelated work on trunk")

    # Precondition the whole bug rests on: the naive ancestor check is TRUE.
    assert is_ancestor(repo, handle.head_sha, _TARGET_BRANCH), (
        "test setup invalid: the worktree HEAD must be an ancestor of trunk for "
        "this regression to exercise the false-positive path"
    )
    return repo, worktree_path


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


def test_nondiverged_worktree_survives_act_mode_sweep(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, worktree_path = _build_nondiverged_state(tmp_path)
    before = _registered_worktrees(repo)
    assert str(worktree_path) in before

    # ACT mode (no --check-only): the destructive path that removed row4.
    exit_code = verify_worktree_cleanup.main(
        ["--repo", str(repo), "--target-branch", _TARGET_BRANCH]
    )
    payload = _last_json_line(capsys.readouterr().out)

    entry = next(e for e in payload["entries"] if e["path"] == str(worktree_path))
    assert entry["verdict"] == "NOT_YET_MERGEABLE", (
        "a worktree with ZERO commits of its own merged nothing -- trunk merely "
        f"advanced past the commit it was cut from. Got verdict={entry['verdict']!r}"
    )
    assert entry["removed"] is False
    assert exit_code == 0

    after = _registered_worktrees(repo)
    assert str(worktree_path) in after, (
        "DATA LOSS: the non-diverged worktree was force-removed by the ACT-mode "
        "sweep even though none of its own work ever merged onto trunk"
    )
