"""Unit tests -- GitWorktreeAdapter.changed_paths_since.

BUGFIX support for
[[impacted-test-selector-selects-everything-and-its-premise-is-false]]: the
drain's post-agent test run needs the REAL set of paths the agent touched,
whether committed, left uncommitted, or both. A small real git repo (init +
one commit) is fast (milliseconds) -- this is not the whole-suite cost the
bug was about.
"""

from __future__ import annotations

import subprocess

from des.adapters.driven.refactor.git_worktree_adapter import GitWorktreeAdapter


def _run(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _init_repo_with_base_commit(repo_path):
    repo_path.mkdir(parents=True, exist_ok=True)
    _run(repo_path, "init", "-q")
    _run(repo_path, "config", "user.email", "test@example.com")
    _run(repo_path, "config", "user.name", "Test")
    (repo_path / "base.txt").write_text("base\n")
    _run(repo_path, "add", "base.txt")
    _run(repo_path, "commit", "-q", "-m", "base")
    base_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return base_sha


def test_a_committed_change_since_base_sha_is_reported(tmp_path):
    repo = tmp_path / "repo"
    base_sha = _init_repo_with_base_commit(repo)
    (repo / "changed.py").write_text("x = 1\n")
    _run(repo, "add", "changed.py")
    _run(repo, "commit", "-q", "-m", "add changed.py")

    adapter = GitWorktreeAdapter()
    changed = adapter.changed_paths_since(repo, base_sha)

    assert "changed.py" in changed


def test_an_uncommitted_change_since_base_sha_is_also_reported(tmp_path):
    repo = tmp_path / "repo"
    base_sha = _init_repo_with_base_commit(repo)
    (repo / "dirty.py").write_text("y = 2\n")

    adapter = GitWorktreeAdapter()
    changed = adapter.changed_paths_since(repo, base_sha)

    assert "dirty.py" in changed


def test_no_change_since_base_sha_reports_nothing(tmp_path):
    repo = tmp_path / "repo"
    base_sha = _init_repo_with_base_commit(repo)

    adapter = GitWorktreeAdapter()
    changed = adapter.changed_paths_since(repo, base_sha)

    assert changed == ()


def test_an_unreachable_base_sha_degrades_to_uncommitted_paths_only(tmp_path):
    repo = tmp_path / "repo"
    _init_repo_with_base_commit(repo)
    (repo / "dirty.py").write_text("z = 3\n")

    adapter = GitWorktreeAdapter()
    changed = adapter.changed_paths_since(repo, "0" * 40)

    assert "dirty.py" in changed
