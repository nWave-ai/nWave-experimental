"""Unit tests for the shared `git-sha1:<hex>` HEAD observation, extracted
from `des.cli.prepare_ordinary_request` for reuse by `des compile-contract`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from des.domain.base_revision_resolver import observed_base_revision


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_root), *args], check=True, capture_output=True
    )


def test_observes_a_real_head_as_git_sha1(tmp_path: Path) -> None:
    (tmp_path / "f.txt").write_text("x", encoding="utf-8")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "test")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "c")

    result = observed_base_revision(tmp_path)
    assert result is not None
    assert result.startswith("git-sha1:")
    assert len(result) == len("git-sha1:") + 40


def test_returns_none_for_a_non_git_directory(tmp_path: Path) -> None:
    assert observed_base_revision(tmp_path) is None
