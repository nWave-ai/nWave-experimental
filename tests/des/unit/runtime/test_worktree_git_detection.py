"""Git-checkout detection distinguishes valid markers from namesakes."""

from __future__ import annotations


# ---------------------------------------------------------------------------
# assert_fresh_or_explain autoskip — worktree FILE case (the regression)
# ---------------------------------------------------------------------------


def test_autoskip_fires_for_git_file_worktree(tmp_path, monkeypatch, capsys):
    """A linked-worktree pointer to an existing gitdir autoskips."""
    gitdir = tmp_path / "common" / "worktrees" / "wt1"
    gitdir.mkdir(parents=True)
    (gitdir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    git_file = tmp_path / ".git"
    git_file.write_text(f"gitdir: {gitdir}\n", encoding="utf-8")

    # Force CWD to tmp_path so the autoskip walk starts there.
    monkeypatch.chdir(str(tmp_path))

    # Ensure the NWAVE_FRESHNESS opt-out is not set (we want the autoskip path).
    monkeypatch.delenv("NWAVE_FRESHNESS", raising=False)
    # Ensure the force-gate override is not set (we want normal autoskip behaviour).
    monkeypatch.delenv("NWAVE_FRESHNESS_FORCE_GATE", raising=False)

    from des.runtime.freshness import assert_fresh_or_explain

    # Must not raise SystemExit(78) — the autoskip should fire and return cleanly.
    assert_fresh_or_explain()  # raises SystemExit on REFUSE; autoskip returns None

    assert capsys.readouterr().err == ""


# ---------------------------------------------------------------------------
# assert_fresh_or_explain autoskip — normal .git DIRECTORY case
# ---------------------------------------------------------------------------


def test_autoskip_fires_for_git_directory(tmp_path, monkeypatch, capsys):
    """A normal checkout directory containing HEAD autoskips."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")

    monkeypatch.chdir(str(tmp_path))
    monkeypatch.delenv("NWAVE_FRESHNESS", raising=False)
    monkeypatch.delenv("NWAVE_FRESHNESS_FORCE_GATE", raising=False)

    from des.runtime.freshness import assert_fresh_or_explain

    assert_fresh_or_explain()

    assert capsys.readouterr().err == ""


def test_verbose_autoskip_names_checkout_reason(tmp_path, monkeypatch, capsys):
    """An operator can request the structural success diagnostic explicitly."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")

    monkeypatch.chdir(str(tmp_path))
    monkeypatch.setenv("NWAVE_FRESHNESS", "verbose")
    monkeypatch.delenv("NWAVE_FRESHNESS_FORCE_GATE", raising=False)

    from des.runtime.freshness import assert_fresh_or_explain

    assert_fresh_or_explain()

    stderr = capsys.readouterr().err
    assert "des.runtime.freshness.autoskipped" in stderr
    assert "adjacency" in stderr


def test_empty_git_named_ancestor_does_not_disable_freshness(
    tmp_path, monkeypatch, capsys
):
    """A stray ancestor named `.git` is not sufficient checkout evidence."""
    (tmp_path / ".git").mkdir()
    cwd = tmp_path / "customer" / "work"
    cwd.mkdir(parents=True)
    monkeypatch.chdir(cwd)
    monkeypatch.delenv("NWAVE_FRESHNESS", raising=False)
    monkeypatch.delenv("NWAVE_FRESHNESS_FORCE_GATE", raising=False)

    from des.runtime.freshness import assert_fresh_or_explain

    try:
        assert_fresh_or_explain()
    except SystemExit as error:
        assert error.code == 78
    else:
        raise AssertionError("manifest-less customer host must refuse")

    stderr = capsys.readouterr().err
    assert "freshness.refused" in stderr
    assert "autoskipped" not in stderr
