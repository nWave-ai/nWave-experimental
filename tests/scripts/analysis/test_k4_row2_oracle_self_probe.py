"""K4 row 2 (`docs/analysis/2026-08-05-des-simplification-evidence-backed-
roadmap.md`, matrix row 2, ~line 426): the acceptance oracle itself once
inverted the verdict (`ef37b76b0` -- a fixture bug flipped which day the
flip landed on, so a CORRECT delivery read as a failure).

`run_acceptance.examine` must refuse to score a pair unless
`_self_probe_oracle_red` has first proven the oracle goes RED against the
workspace's OWN undelivered base commit -- GDP-8's witness corollary: the
checker is not exempt from the class it checks. These tests drive that gate
with a fake subject runner that plants both a healthy self-probe (RED, as an
undelivered subject must read) and a broken one (GREEN, the silent-pass
failure mode this gate exists to catch), never a real Django/git subprocess.

Run: uv run pytest -q tests/scripts/analysis/test_k4_row2_oracle_self_probe.py
"""

from __future__ import annotations

import subprocess

from scripts.analysis.k4 import run_acceptance as ra


def _git(*args: str, cwd) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _workspace(tmp_path):
    workspace = tmp_path / "delivery"
    (workspace / "hc" / "api" / "tests").mkdir(parents=True)
    (workspace / "manage.py").write_text("# django manage.py stub\n")
    (workspace / "requirements.txt").write_text("# no real deps\n")
    suite = tmp_path / "suite.py"
    suite.write_text("# hidden suite\n")
    _git("init", "-q", "-b", "master", cwd=workspace)
    _git("config", "user.email", "k4@example.test", cwd=workspace)
    _git("config", "user.name", "k4", cwd=workspace)
    _git("add", "-A", cwd=workspace)
    _git("commit", "-q", "-m", "seed", cwd=workspace)
    return workspace, suite


def _fake_subject_runner(
    *,
    self_probe_exit: int,
    main_feature_exit: int = 0,
    main_regression_exit: int = 0,
    calls: list[tuple[tuple[str, ...], str]] | None = None,
):
    """A fake `_run` standing in for the whole subject toolchain (venv, pip,
    `manage.py test`). It distinguishes the row-2 self-probe's own suite run
    -- its cwd always carries `_SELF_PROBE_DIR_MARKER`, see
    `_self_probe_oracle_red` -- from the main scored run's two suites, so a
    test can dial the self-probe's verdict independently of the delivery's."""

    def fake(argv, cwd, timeout=2400):
        if calls is not None:
            calls.append((tuple(argv), str(cwd)))
        if ra._SELF_PROBE_DIR_MARKER in str(cwd):
            if ra._SUITE_LABEL in argv:
                return self_probe_exit, (
                    "OK: planted GREEN" if self_probe_exit == 0 else "FAIL: planted RED"
                )
            return 0, ""  # the self-probe's own venv/pip install steps
        if "venv" in argv or "install" in argv:
            return 0, ""
        if ra._SUITE_LABEL in argv:
            return main_feature_exit, "OK" if main_feature_exit == 0 else "FAILED"
        if "--exclude-tag" in argv:
            return main_regression_exit, "OK" if main_regression_exit == 0 else "FAILED"
        raise AssertionError(f"unexpected argv: {argv}")

    return fake


def test_examine_refuses_when_the_oracle_does_not_prove_red_on_the_undelivered_base(
    tmp_path, monkeypatch
):
    """RED->GREEN falsifier for row 2: an oracle whose self-probe exits 0
    (GREEN) against the workspace's own undelivered base -- exactly the
    historical defect class, an oracle that cannot discriminate delivered
    from undelivered -- must never be trusted to score anything, however
    clean the 'delivery' run itself looks."""
    workspace, suite = _workspace(tmp_path)
    monkeypatch.setattr(ra, "_run", _fake_subject_runner(self_probe_exit=0))

    accepted, evidence = ra.examine(workspace, suite)

    assert accepted is False
    assert "did not prove RED" in evidence
    assert "undelivered base" in evidence


def test_examine_scores_normally_once_the_oracle_proves_red(tmp_path, monkeypatch):
    """The healthy path: a self-probe that DOES go RED on the undelivered
    base clears the gate, and the pair is scored on its own merits."""
    workspace, suite = _workspace(tmp_path)
    monkeypatch.setattr(ra, "_run", _fake_subject_runner(self_probe_exit=1))

    accepted, evidence = ra.examine(workspace, suite)

    assert accepted is True
    assert "hidden suite exit 0" in evidence


def test_examine_still_refuses_when_the_oracle_proves_red_but_the_delivery_fails(
    tmp_path, monkeypatch
):
    """The gate and the score are independent axes: a proven-RED oracle does
    not make a failing delivery pass."""
    workspace, suite = _workspace(tmp_path)
    monkeypatch.setattr(
        ra, "_run", _fake_subject_runner(self_probe_exit=1, main_feature_exit=1)
    )

    accepted, evidence = ra.examine(workspace, suite)

    assert accepted is False
    assert "did not prove RED" not in evidence  # refused by the SCORE, not the gate
    assert "hidden suite exit 1" in evidence


def test_self_probe_runs_once_per_base_commit_across_a_shared_cache(
    tmp_path, monkeypatch
):
    """Cheap, per row 2's ask: two pairs sharing one base commit (the normal
    case -- every pair in a campaign clones the same SUT) must not each pay
    for their own self-probe; `main` shares one `probe_cache` across the
    whole campaign loop for exactly this reason."""
    workspace, suite = _workspace(tmp_path)
    calls: list[tuple[tuple[str, ...], str]] = []
    monkeypatch.setattr(
        ra, "_run", _fake_subject_runner(self_probe_exit=1, calls=calls)
    )

    probe_cache: dict[str, tuple[bool, str]] = {}
    first = ra.examine(workspace, suite, probe_cache=probe_cache)
    second = ra.examine(workspace, suite, probe_cache=probe_cache)

    assert first[0] is True
    assert second[0] is True
    probe_suite_calls = [
        c
        for c in calls
        if ra._SELF_PROBE_DIR_MARKER in c[1] and ra._SUITE_LABEL in c[0]
    ]
    assert len(probe_suite_calls) == 1, (
        "expected exactly one self-probe suite run across both pairs sharing "
        f"the same base commit, got {len(probe_suite_calls)}"
    )


def test_examine_refuses_when_the_workspace_has_no_resolvable_base_commit(
    tmp_path, monkeypatch
):
    """A workspace this harness cannot resolve a base commit for (no `.git`
    at all) is refused loud, never scored on faith -- and never even reaches
    `_run`, since there is nothing to self-probe against."""
    workspace = tmp_path / "delivery"
    (workspace / "hc" / "api" / "tests").mkdir(parents=True)
    (workspace / "manage.py").write_text("# django manage.py stub\n")
    suite = tmp_path / "suite.py"
    suite.write_text("# hidden suite\n")
    monkeypatch.setattr(
        ra,
        "_run",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run")),
    )

    accepted, evidence = ra.examine(workspace, suite)

    assert accepted is False
    assert "base commit" in evidence
