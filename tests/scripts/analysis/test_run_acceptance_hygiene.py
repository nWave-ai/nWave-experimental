"""Hidden-suite hygiene: `run_acceptance.examine` must never leave the
generated `hc/api/tests/test_k4_acceptance.py` behind, and must never delete
one that was already there.

Contaminated blind review found this: the hidden test stayed in the delivery
tree after every run, so a reviewer reading the tree could see it. The base
version copies the suite in and never removes it -- these tests go RED against
that and GREEN once `examine` cleans up in a `finally`, regardless of whether
the hidden suite passed, failed, raised, or timed out.

Run: uv run pytest -q tests/scripts/analysis/test_run_acceptance_hygiene.py
"""

from __future__ import annotations

import subprocess

import pytest

from scripts.analysis.k4 import run_acceptance as ra


def _git(*args: str, cwd) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


_TARGET = ra._SUITE_TARGET  # hc/api/tests/test_k4_acceptance.py, relative


def _workspace(tmp_path):
    workspace = tmp_path / "delivery"
    (workspace / "hc" / "api" / "tests").mkdir(parents=True)
    (workspace / "manage.py").write_text("# django manage.py stub\n")
    suite = tmp_path / "suite.py"
    suite.write_text("# hidden suite\n")
    # Row 2, K4 matrix: `examine` now refuses to score anything until the
    # row-2 self-probe (GDP-8 witness corollary) has proven the oracle goes
    # RED on this workspace's own base commit -- resolved via REAL git,
    # never the mockable `_run` seam (see `_base_commit_sha`). Every
    # workspace under test needs a real commit to serve as that base.
    _git("init", "-q", "-b", "master", cwd=workspace)
    _git("config", "user.email", "k4@example.test", cwd=workspace)
    _git("config", "user.name", "k4", cwd=workspace)
    _git("add", "-A", cwd=workspace)
    _git("commit", "-q", "-m", "seed", cwd=workspace)
    return workspace, suite


def _stub_run(*, feature=(0, "OK"), regression=(0, "OK"), raise_on=None):
    """A drop-in for `_run` that skips real subprocesses entirely.

    The row-2 self-probe runs the SAME `_SUITE_LABEL` command this fake
    already recognizes, but in its own extracted-base snapshot (tagged
    `_SELF_PROBE_DIR_MARKER` in its cwd) rather than the delivery snapshot
    these tests exercise -- so it is matched FIRST and always answers RED,
    true to what an undelivered subject actually does, letting every
    existing assertion here keep measuring what it always measured.
    """

    def fake(argv, cwd, timeout=2400):
        joined = " ".join(argv)
        if raise_on and raise_on in joined:
            raise RuntimeError(f"boom during: {joined}")
        if ra._SELF_PROBE_DIR_MARKER in str(cwd) and ra._SUITE_LABEL in argv:
            return 1, "FAIL: self-probe -- undelivered base, as expected"
        if "venv" in argv:
            return 0, ""
        if "install" in argv:
            return 0, ""
        if ra._SUITE_LABEL in argv:
            return feature
        if "--exclude-tag" in argv:
            return regression
        raise AssertionError(f"unexpected argv: {argv}")

    return fake


@pytest.mark.parametrize(
    "kwargs",
    [
        pytest.param({}, id="both-suites-pass"),
        pytest.param({"feature": (1, "FAILED (failures=1)")}, id="hidden-suite-fails"),
        pytest.param(
            {"regression": (1, "FAILED (failures=2)")}, id="subject-suite-fails"
        ),
        pytest.param(
            {"feature": (124, "TIMEOUT after 2400s")}, id="hidden-suite-times-out"
        ),
    ],
)
def test_generated_suite_is_always_removed(tmp_path, monkeypatch, kwargs):
    workspace, suite = _workspace(tmp_path)
    monkeypatch.setattr(ra, "_run", _stub_run(**kwargs))

    ra.examine(workspace, suite)

    assert not (workspace / _TARGET).exists()


def test_generated_suite_is_removed_even_if_the_run_raises(tmp_path, monkeypatch):
    workspace, suite = _workspace(tmp_path)
    monkeypatch.setattr(ra, "_run", _stub_run(raise_on=ra._SUITE_LABEL))

    with pytest.raises(RuntimeError):
        ra.examine(workspace, suite)

    assert not (workspace / _TARGET).exists()


def test_preexisting_suite_file_is_a_refusal_not_a_deletion(tmp_path, monkeypatch):
    workspace, suite = _workspace(tmp_path)
    preexisting = workspace / _TARGET
    preexisting.write_text("pre-existing content, not ours to touch\n")
    monkeypatch.setattr(
        ra,
        "_run",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run")),
    )

    accepted, evidence = ra.examine(workspace, suite)

    assert accepted is False
    assert "already contains" in evidence
    assert preexisting.read_text() == "pre-existing content, not ours to touch\n"


def test_accepted_requires_both_suites_to_pass(tmp_path, monkeypatch):
    workspace, suite = _workspace(tmp_path)
    monkeypatch.setattr(ra, "_run", _stub_run())

    accepted, _ = ra.examine(workspace, suite)

    assert accepted is True
    assert not (workspace / _TARGET).exists()


def test_user_environment_fixture_artifact_is_absent_and_workspace_git_clean_after_examine(
    tmp_path, monkeypatch
):
    """A stale `.k4-user-environment.md` left in the workspace must not
    survive `examine`: it is gone from the filesystem and the workspace
    reports a clean `git status` once `examine` returns, the same hygiene
    guarantee as the hidden suite file above, so a reviewer never sees it
    either. How cleanup is achieved is an implementation detail this test
    does not pin down."""
    from scripts.analysis.k4 import prepare_examiner_fixture as pef

    workspace, suite = _workspace(tmp_path)  # already a git repo with one commit

    leftover = workspace / pef.DOC_NAME
    leftover.write_text("stale user-environment fixture doc\n")

    monkeypatch.setattr(ra, "_run", _stub_run())

    ra.examine(workspace, suite)

    assert not leftover.exists(), (
        "the user-environment fixture artifact must not survive `examine`, "
        "not be left for a reviewer to find"
    )
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=True,
    )
    assert status.stdout.strip() == "", (
        f"workspace must be git-clean after examine: {status.stdout!r}"
    )
