"""Unit tests for GitCommitTreePathAdapter's degrade-LOUD contract.

Mirrors ``test_committed_scope_adapter.py``'s mocked-``subprocess.run`` shape
(the established pattern for this adapter family): git absent or a
non-work-tree degrades to ``Indeterminate``, never a crash and never a
silent pass; a resolvable commit with a genuinely absent path is a
DEFINITIVE ``False``, never conflated with "could not tell".
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from des.adapters.driven.git.git_commit_tree_path_adapter import (
    GitCommitTreePathAdapter,
)
from des.ports.driven_ports.commit_tree_path_port import Indeterminate


def test_git_binary_missing_degrades_to_indeterminate_not_a_crash() -> None:
    adapter = GitCommitTreePathAdapter()
    with patch(
        "subprocess.run",
        side_effect=FileNotFoundError("[Errno 2] No such file or directory: 'git'"),
    ):
        result = adapter.path_exists_at_commit(Path("/repo"), "deadbeef" * 5, "a.py")
    assert isinstance(result, Indeterminate)
    assert "git" in result.reason.lower()


def test_unresolvable_commit_degrades_to_indeterminate() -> None:
    """The commit-resolution probe (`{sha}^{commit}`) fails -- Indeterminate,
    never a False (a bad sha must never masquerade as "path absent")."""
    adapter = GitCommitTreePathAdapter()
    failed = MagicMock()
    failed.returncode = 128
    failed.stdout = ""
    failed.stderr = "fatal: Not a valid object name deadbeef^{commit}\n"
    with patch("subprocess.run", return_value=failed):
        result = adapter.path_exists_at_commit(Path("/repo"), "deadbeef" * 5, "a.py")
    assert isinstance(result, Indeterminate)
    assert "deadbeef" in result.reason


def test_not_a_work_tree_degrades_to_indeterminate() -> None:
    adapter = GitCommitTreePathAdapter()
    failed = MagicMock()
    failed.returncode = 128
    failed.stdout = ""
    failed.stderr = "fatal: not a git repository (or any parent up to mount point /)\n"
    with patch("subprocess.run", return_value=failed):
        result = adapter.path_exists_at_commit(Path("/not-a-repo"), "a" * 40, "a.py")
    assert isinstance(result, Indeterminate)


def test_resolvable_commit_missing_path_is_definitively_false() -> None:
    """Commit resolves (first call ok), path probe fails (second call
    non-zero, not "not a git repository") -- a DEFINITIVE False, the exact
    fact a premature-seal check depends on."""
    adapter = GitCommitTreePathAdapter()

    commit_ok = MagicMock()
    commit_ok.returncode = 0
    commit_ok.stdout = ""
    commit_ok.stderr = ""

    path_missing = MagicMock()
    path_missing.returncode = 128
    path_missing.stdout = ""
    path_missing.stderr = "fatal: path 'a.py' does not exist in 'abc123'\n"

    with patch("subprocess.run", side_effect=[commit_ok, path_missing]):
        result = adapter.path_exists_at_commit(Path("/repo"), "a" * 40, "a.py")
    assert result is False


def test_resolvable_commit_present_path_is_true() -> None:
    adapter = GitCommitTreePathAdapter()

    commit_ok = MagicMock()
    commit_ok.returncode = 0
    commit_ok.stdout = ""
    commit_ok.stderr = ""

    path_ok = MagicMock()
    path_ok.returncode = 0
    path_ok.stdout = ""
    path_ok.stderr = ""

    with patch("subprocess.run", side_effect=[commit_ok, path_ok]):
        result = adapter.path_exists_at_commit(Path("/repo"), "a" * 40, "a.py")
    assert result is True


def test_real_repo_end_to_end(tmp_path: Path) -> None:
    """No mocking: a real git repo, a real commit, a real path check --
    guards the two hand-mocked cases above against drifting from real git
    output shapes."""
    import subprocess

    def _git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=tmp_path, check=True, capture_output=True, text=True
        ).stdout

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True
    )
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "before.txt").write_text("x", encoding="utf-8")
    _git("add", "-A")
    _git("commit", "-q", "-m", "before")
    before_sha = _git("rev-parse", "HEAD").strip()

    (tmp_path / "after.txt").write_text("y", encoding="utf-8")
    _git("add", "-A")
    _git("commit", "-q", "-m", "after")

    adapter = GitCommitTreePathAdapter()
    assert adapter.path_exists_at_commit(tmp_path, before_sha, "before.txt") is True
    assert adapter.path_exists_at_commit(tmp_path, before_sha, "after.txt") is False
    bogus = "1234567890abcdef1234567890abcdef12345678"
    assert isinstance(
        adapter.path_exists_at_commit(tmp_path, bogus, "before.txt"), Indeterminate
    )
