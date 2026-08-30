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


# --- the full-clone regression (camp7, 2026-08-23) --------------------------
#
# `c8622cf32` replaced `git clone --depth 1 <SUT> .` with a FULL clone plus
# `git checkout --detach <SUT_PINNED_REV>`, and added `examine`'s
# `pinned_subject_rev` cross-check -- but left `_base_commit_sha` deriving the
# base from `git rev-list --max-parents=0 HEAD`, which is the SHALLOW clone's
# tip and, in a full clone, the subject's FIRST COMMIT EVER. Measured on
# camp7's paid workspaces: root `00cdc313`, HEAD `49653c35` (== the pin), no
# `.git/shallow` file -- so every arm of every campaign was refused for "not
# matching the pin" before the hidden suite or the row-2 RED probe ever ran.


def _full_clone_shaped_workspace(tmp_path, *, delivery_commit: bool = False):
    """A workspace with the shape `preflight.py` actually produces since
    `c8622cf32`: real history behind the checked-out commit, HEAD detached at
    the pin, the delivery sitting in the working tree (or, optionally, in a
    commit on top of the pin)."""
    import subprocess

    def _git(*args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=workspace,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    workspace = tmp_path / "delivery"
    (workspace / "hc" / "api" / "tests").mkdir(parents=True)
    (workspace / "manage.py").write_text("# django manage.py stub\n")
    (workspace / "requirements.txt").write_text("# no real deps\n")
    suite = tmp_path / "suite.py"
    suite.write_text("# hidden suite\n")

    _git("init", "-q", "-b", "master")
    _git("config", "user.email", "k4@example.test")
    _git("config", "user.name", "k4")
    _git("add", "-A")
    _git("commit", "-q", "-m", "first commit ever")
    for n in (1, 2):
        (workspace / "CHANGELOG.md").write_text(f"history {n}\n")
        _git("add", "-A")
        _git("commit", "-q", "-m", f"upstream history {n}")
    pin = _git("rev-parse", "HEAD")
    _git("checkout", "-q", "--detach", pin)
    if delivery_commit:
        (workspace / "hc" / "api" / "feature.py").write_text("# delivered\n")
        _git("add", "-A")
        _git("commit", "-q", "-m", "the delivery")
    return workspace, suite, pin


def test_base_commit_is_the_declared_pin_not_the_full_clones_root_commit(tmp_path):
    """RED->GREEN falsifier: the base commit is READ from the campaign's
    declared pin, never re-derived from the shape of the clone."""
    workspace, _suite, pin = _full_clone_shaped_workspace(tmp_path)

    base, why = run_acceptance._base_commit_sha(workspace, pin)

    assert base == pin, f"resolved {base!r} instead of the declared pin {pin!r}: {why}"


def test_examine_scores_a_full_clone_workspace_instead_of_refusing_it(
    tmp_path, monkeypatch
):
    """The behavioural falsifier, in miniature: camp7's arm shape (full
    history, HEAD detached at the pin, delivery in the working tree) must
    reach the oracle, not be refused before it."""
    from tests.scripts.analysis.test_k4_row2_oracle_self_probe import (
        _fake_subject_runner,
    )

    workspace, suite, pin = _full_clone_shaped_workspace(tmp_path)
    monkeypatch.setattr(run_acceptance, "_run", _fake_subject_runner(self_probe_exit=1))

    accepted, evidence = run_acceptance.examine(
        workspace, suite, pinned_subject_rev=pin
    )

    assert accepted is True, evidence
    assert "hidden suite exit 0" in evidence


def test_examine_scores_a_workspace_whose_delivery_committed_on_top_of_the_pin(
    tmp_path, monkeypatch
):
    """The pin is the base whether the delivery committed or not: reachable
    from HEAD is the property, equality with HEAD is not."""
    from tests.scripts.analysis.test_k4_row2_oracle_self_probe import (
        _fake_subject_runner,
    )

    workspace, suite, pin = _full_clone_shaped_workspace(tmp_path, delivery_commit=True)
    monkeypatch.setattr(run_acceptance, "_run", _fake_subject_runner(self_probe_exit=1))

    accepted, evidence = run_acceptance.examine(
        workspace, suite, pinned_subject_rev=pin
    )

    assert accepted is True, evidence


def test_examine_refuses_a_workspace_whose_history_does_not_carry_the_pin(
    tmp_path, monkeypatch
):
    """The check the pin exists FOR, restated on the repaired semantics: a
    workspace that never sat on the declared subject revision is refused --
    a stale workspace from before pinning, or a preflight bug."""
    workspace, suite, _pin = _full_clone_shaped_workspace(tmp_path)
    monkeypatch.setattr(
        run_acceptance,
        "_run",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run")),
    )

    accepted, evidence = run_acceptance.examine(
        workspace, suite, pinned_subject_rev="not-the-real-pin"
    )

    assert accepted is False
    assert "not-the-real-pin" in evidence
