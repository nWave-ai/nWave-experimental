"""Regression pin: linked git worktree `.git` FILE support.

RCA: the `assert_fresh_or_explain` autoskip walk used `os.path.isdir` to detect
`.git`, making it blind to linked worktrees where `.git` is a FILE containing
`gitdir: <common-dir>/worktrees/<name>`.

Fix: the predicate changed to `os.path.exists` so a `.git` file OR directory
are both recognised as a developer-checkout / repo-root marker.

The tested function has a companion pair:
  - `.git` is a FILE  → must be detected (the regression case)
  - `.git` is a DIR   → must still be detected (the existing behaviour)
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# assert_fresh_or_explain autoskip — worktree FILE case (the regression)
# ---------------------------------------------------------------------------


def test_autoskip_fires_for_git_file_worktree(tmp_path, monkeypatch, capsys):
    """assert_fresh_or_explain autoskip fires when .git is a FILE (worktree pointer).

    The autoskip walk uses os.path.exists (post-fix), so a .git file is treated
    as a developer checkout and the function returns early without calling
    RepoSourceProbe, which would fail with DEGRADED / exit 78 on a manifest-less
    tmp directory.
    """
    # Create a .git FILE in tmp_path, simulating a linked worktree.
    git_file = tmp_path / ".git"
    git_file.write_text("gitdir: /some/common/.git/worktrees/wt1\n")

    # Force CWD to tmp_path so the autoskip walk starts there.
    monkeypatch.chdir(str(tmp_path))

    # Ensure the NWAVE_FRESHNESS opt-out is not set (we want the autoskip path).
    monkeypatch.delenv("NWAVE_FRESHNESS", raising=False)
    # Ensure the force-gate override is not set (we want normal autoskip behaviour).
    monkeypatch.delenv("NWAVE_FRESHNESS_FORCE_GATE", raising=False)

    from des.runtime.freshness import assert_fresh_or_explain

    # Must not raise SystemExit(78) — the autoskip should fire and return cleanly.
    assert_fresh_or_explain()  # raises SystemExit on REFUSE; autoskip returns None

    stderr = capsys.readouterr().err
    assert "autoskipped" in stderr
    assert "adjacency" in stderr


# ---------------------------------------------------------------------------
# assert_fresh_or_explain autoskip — normal .git DIRECTORY case
# ---------------------------------------------------------------------------


def test_autoskip_fires_for_git_directory(tmp_path, monkeypatch, capsys):
    """assert_fresh_or_explain autoskip fires when .git is a DIRECTORY (normal checkout)."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    monkeypatch.chdir(str(tmp_path))
    monkeypatch.delenv("NWAVE_FRESHNESS", raising=False)
    monkeypatch.delenv("NWAVE_FRESHNESS_FORCE_GATE", raising=False)

    from des.runtime.freshness import assert_fresh_or_explain

    assert_fresh_or_explain()

    stderr = capsys.readouterr().err
    assert "autoskipped" in stderr
    assert "adjacency" in stderr
