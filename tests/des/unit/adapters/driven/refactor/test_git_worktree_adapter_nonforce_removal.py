from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from des.adapters.driven.refactor.git_worktree_adapter import GitWorktreeAdapter


def test_nonforce_removal_preserves_a_toctou_dirty_worktree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    lane = tmp_path / "lane"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.test"], cwd=repo, check=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "seed.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)
    subprocess.run(
        ["git", "worktree", "add", "-b", "lane", str(lane), "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (lane / "late-write.txt").write_text("arrived after preflight\n", encoding="utf-8")

    with pytest.raises(subprocess.CalledProcessError):
        GitWorktreeAdapter().remove_worktree(repo, lane)

    assert lane.exists()
    assert (lane / "late-write.txt").exists()
    registered = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert str(lane) in registered
