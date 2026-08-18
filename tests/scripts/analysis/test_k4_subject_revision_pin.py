"""K4 addendum to row 2/4 (docs/analysis/2026-08-05-des-simplification-
evidence-backed-roadmap.md matrix, ~line 426): the campaign used to clone
healthchecks fresh and UNPINNED every run (`git clone --depth 1 <SUT> .`,
whatever the default branch's tip happened to be at that exact moment).
Reproducibility needs one pinned base revision, declared in exactly ONE
place -- `scripts/analysis/k4/subject.SUT_PINNED_REV`, the same commit the
row-2 self-probe (`test_k4_row2_oracle_self_probe.py`) was validated
against by hand -- that `preflight.py` (clones and checks it out),
`run_acceptance.py` (cross-checks a scored pair's own base commit against
it), and `paired_campaign.py` (compares the `git checkout` target BOTH arms
declared, generically, never importing the K4-specific constant) all read.

Run: uv run pytest -q tests/scripts/analysis/test_k4_subject_revision_pin.py
"""

from __future__ import annotations

from pathlib import Path

from scripts.analysis.k4 import preflight, run_acceptance, subject
from scripts.analysis.paired_campaign import ArmSpec, declared_identity_violations


def _fake_clone_runner(steps):
    """Stands in for the real subprocess executor `preflight.py`'s declared
    setup steps run under (see `paired_campaign._run_setup`): records every
    invoked argv instead of touching the network or the filesystem, so a
    test can assert exactly what a clone/checkout was INVOKED with."""
    invoked: list[tuple[str, ...]] = []
    for step in steps:
        invoked.append(tuple(step))
    return invoked


def test_nwave_arm_checkout_step_is_invoked_with_the_pinned_revision():
    """RED->GREEN falsifier: the declared checkout step must name the exact
    pinned commit, not `HEAD` or any other moving target."""
    steps = preflight.nwave_setup_steps(Path("/venv"), Path("/auth"))
    invoked = _fake_clone_runner(steps)

    checkout_calls = [c for c in invoked if c[:2] == ("git", "checkout")]
    assert len(checkout_calls) == 1, (
        f"expected exactly one checkout step, got {invoked}"
    )
    assert checkout_calls[0][-1] == subject.SUT_PINNED_REV, (
        f"the nwave arm's checkout step was invoked with {checkout_calls[0]!r}, "
        f"not the pinned revision {subject.SUT_PINNED_REV!r}"
    )


def test_control_arm_checkout_step_is_invoked_with_the_pinned_revision():
    steps = preflight.control_setup_steps(Path("/auth"))
    invoked = _fake_clone_runner(steps)

    checkout_calls = [c for c in invoked if c[:2] == ("git", "checkout")]
    assert len(checkout_calls) == 1, (
        f"expected exactly one checkout step, got {invoked}"
    )
    assert checkout_calls[0][-1] == subject.SUT_PINNED_REV, (
        f"the control arm's checkout step was invoked with {checkout_calls[0]!r}, "
        f"not the pinned revision {subject.SUT_PINNED_REV!r}"
    )


def test_both_arms_pin_to_the_identical_revision():
    """Both arms of every pair must be measured against the SAME subject
    state, not merely each pinned to SOME revision independently."""
    control = _fake_clone_runner(preflight.control_setup_steps(Path("/auth")))
    nwave = _fake_clone_runner(
        preflight.nwave_setup_steps(Path("/venv"), Path("/auth"))
    )

    control_target = next(c[-1] for c in control if c[:2] == ("git", "checkout"))
    nwave_target = next(c[-1] for c in nwave if c[:2] == ("git", "checkout"))

    assert control_target == nwave_target == subject.SUT_PINNED_REV


def test_declared_identity_violations_refuses_arms_pinned_to_different_revisions():
    """`paired_campaign.py` stays subject-agnostic (its own module docstring:
    "this module knows nothing about any harness") -- it never imports
    `subject.SUT_PINNED_REV` directly, but it MUST catch two arms whose own
    declared `git checkout` steps disagree, since that is exactly the
    confound row 2/4 reproducibility cares about."""
    control = ArmSpec(
        "control",
        ("claude", "-p", "{task}"),
        (
            ("git", "clone", subject.SUT_URL, "."),
            ("git", "checkout", "--detach", "aaa"),
        ),
    )
    nwave = ArmSpec(
        "nwave",
        ("claude", "-p", "{task}"),
        (
            ("git", "clone", subject.SUT_URL, "."),
            ("git", "checkout", "--detach", "bbb"),
        ),
    )

    problems = declared_identity_violations([control, nwave])

    assert any("checkout" in p and "differ" in p for p in problems), problems


def test_declared_identity_violations_passes_arms_pinned_to_the_same_revision():
    control = ArmSpec(
        "control",
        ("claude", "-p", "{task}"),
        (
            ("git", "clone", subject.SUT_URL, "."),
            ("git", "checkout", "--detach", subject.SUT_PINNED_REV),
        ),
    )
    nwave = ArmSpec(
        "nwave",
        ("claude", "-p", "{task}"),
        (
            ("git", "clone", subject.SUT_URL, "."),
            ("git", "checkout", "--detach", subject.SUT_PINNED_REV),
        ),
    )

    assert declared_identity_violations([control, nwave]) == []


def test_examine_refuses_a_pair_whose_own_base_commit_disagrees_with_the_pin(
    tmp_path, monkeypatch
):
    """`run_acceptance.examine`'s `pinned_subject_rev` parameter (what `main`
    passes as `subject.SUT_PINNED_REV`) catches a pair measured against a
    base commit that is internally self-consistent (the self-probe alone
    would happily prove RED on it) but is NOT the campaign's declared pin --
    e.g. a stale workspace from before pinning, or a preflight bug."""
    import subprocess

    def _git(*args: str, cwd) -> None:
        subprocess.run(
            ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
        )

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

    monkeypatch.setattr(
        run_acceptance,
        "_run",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run")),
    )

    accepted, evidence = run_acceptance.examine(
        workspace, suite, pinned_subject_rev="not-the-real-pin"
    )

    assert accepted is False
    assert "does not match the pinned subject revision" in evidence
    assert "not-the-real-pin" in evidence
