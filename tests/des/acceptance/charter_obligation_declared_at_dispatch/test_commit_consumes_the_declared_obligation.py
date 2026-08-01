# @feature-charter-obligation-declared-at-dispatch
"""ATs -- the commit CONSUMES the declared obligation.

Feature `charter-obligation-declared-at-dispatch`, Slice Plan row 2:
"When I go to commit work that was declared as user-visible but has no charter,
the system stops me and hands me the exact command that writes one."

CONTRACT_SHAPE: bounded-change (the commit's declared mutation set is unchanged
for EXEMPT and INDETERMINATE; for REQUIRED-without-charter it is empty and the
refusal is the observable).

Driving surface: the production `des` CLI EDGE driven IN-PROCESS (L2 default).
The Given of every scenario runs the REAL producer -- `des dispatch` -- so the
declaration under test is the one the system actually writes, never a fixture
the test fabricated (Pillar 2 chained narrative, Pillar 3 app-as-in-production).

ACTIVE-RED TODAY. `_examine_gate_armed` (`commit_slice.py:723-736`) returns a
two-valued `bool` computed from the presence of a charter DIRECTORY; it never
reads a declaration, so `CharterObligationUnmet` and `ExamineArmingIndeterminate`
are emitted by nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.des.acceptance.charter_obligation_declared_at_dispatch.composition import (
    FEATURE_ID,
    commit_slice,
    dispatch,
    emitted_events,
    event_named,
    provision_project,
    verify_slice_commit_completeness,
)
from tests.des.acceptance.charter_obligation_declared_at_dispatch.domain_types import (
    ARMING_INDETERMINATE_EVENT,
    OBLIGATION_UNMET_EVENT,
)


SLICE_ID = "slice-01"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return provision_project(tmp_path / "project")


def _work_to_commit(project: Path) -> None:
    """A new file so the commit has something to carry."""
    target = project / "tests" / "unit" / "test_new_behaviour.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("def test_new_behaviour():\n    assert True\n", encoding="utf-8")


def _commit_outcome(project: Path) -> tuple[int, list[dict[str, object]], str]:
    exit_code, stdout, stderr = commit_slice(project, SLICE_ID)
    return exit_code, emitted_events(stdout, stderr), f"{stdout}\n{stderr}"


def _obligation_attestation(
    events: list[dict[str, object]],
) -> dict[str, object] | None:
    """The emitted event that ATTESTS which obligation the commit resolved.

    A structured attestation, never a substring search: the E1 zero-evidence
    refusal's own HOW text already contains the word `@prefactoring`, so a bare
    `"prefactoring" in output` check passes by accident today and would keep
    passing with the feature deleted.
    """
    for record in events:
        if "obligation" in record and record.get("slice_id") in (None, SLICE_ID):
            return record
    return None


# ---------------------------------------------------------------------------
# REQUIRED -- the gate fires, and its HOW is runnable
# ---------------------------------------------------------------------------


def test_declared_user_visible_work_without_a_charter_is_stopped_with_the_command(
    project: Path,
) -> None:
    """@driving_port @real-io @error

    The whole value of the slice: the refusal does not merely say no, it hands
    over the exact producing-tool invocation that makes the artifact valid
    (GDP-4). A bare `FAILED` would leave the operator to investigate.
    """
    # covers: R8
    dispatch(project, SLICE_ID, lane="bugfix")
    _work_to_commit(project)

    exit_code, events, rendered = _commit_outcome(project)

    refusal = event_named(events, OBLIGATION_UNMET_EVENT)
    assert refusal is not None, (
        f"work declared REQUIRED with no charter committed without a "
        f"{OBLIGATION_UNMET_EVENT!r} refusal. exit={exit_code}, "
        f"events={[e.get('event') for e in events]}, output={rendered[-1200:]!r}"
    )
    assert exit_code == 2, f"expected exit 2, got {exit_code}; refusal={refusal!r}"
    for key in ("what", "why", "how"):
        assert str(refusal.get(key, "")).strip(), (
            f"the refusal is missing a {key!r} -- every rejection states WHAT "
            f"failed, WHY, and HOW to fix: {refusal!r}"
        )
    how = str(refusal.get("how", ""))
    for fragment in (
        "des charter-scaffold",
        f"--feature-id {FEATURE_ID}",
        "--seed-mode bug-observable",
        "--observable",
    ):
        assert fragment in how, (
            f"the HOW must interpolate the full producing-tool line; "
            f"{fragment!r} is missing from {how!r}"
        )


def test_a_filled_charter_clears_the_obligation_that_the_refusal_named(
    project: Path,
) -> None:
    """@driving_port @real-io

    NEGATIVE observation: the gate must NOT fire once the obligation is met.
    A gate that refuses even after the operator ran the command it printed is
    worse than no gate.
    """
    # covers: R8
    dispatch(project, SLICE_ID, lane="bugfix")
    charter_dir = project / "docs" / "product" / "expectations" / FEATURE_ID
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "intent.md").write_text(
        "# Intent\n\nSpec rows: slice-01\n", encoding="utf-8"
    )
    _work_to_commit(project)

    _exit_code, events, rendered = _commit_outcome(project)

    assert event_named(events, OBLIGATION_UNMET_EVENT) is None, (
        "the charter exists, so the obligation is met -- the gate must not "
        f"still refuse. output={rendered[-1200:]!r}"
    )
    assert _obligation_attestation(events) is not None, (
        "an absence-only assertion passes while nothing exists at all. The "
        "clearance must POSITIVELY attest that the REQUIRED obligation was "
        "checked and met, so 'cleared' can be told from 'never looked'. "
        f"events={[e.get('event') for e in events]}, output={rendered[-1200:]!r}"
    )


# ---------------------------------------------------------------------------
# EXEMPT vs NEVER-DECLARED -- the discriminator, at the consuming surface
# ---------------------------------------------------------------------------


def test_declared_exempt_work_is_not_stopped_and_the_reason_is_shown(
    project: Path,
) -> None:
    """@driving_port @real-io

    NEGATIVE observation. A `prefactoring` lane already declares
    behaviour-preservation (`GuardKind.GREEN_TO_GREEN`, `lane_profile.py:73-75`).
    The gate must not fire -- and the clearance must ATTEST its reason, so an
    operator can tell a cleared obligation from an unchecked one.
    """
    # covers: R9
    dispatch(project, SLICE_ID, lane="prefactoring")
    _work_to_commit(project)

    _exit_code, events, rendered = _commit_outcome(project)

    assert event_named(events, OBLIGATION_UNMET_EVENT) is None, (
        "work DECLARED EXEMPT was stopped by the charter-obligation gate; "
        f"output={rendered[-1200:]!r}"
    )
    assert event_named(events, ARMING_INDETERMINATE_EVENT) is None, (
        "declared-EXEMPT work must not be reported as INDETERMINATE -- the "
        f"operator DID declare. output={rendered[-1200:]!r}"
    )
    attestation = _obligation_attestation(events)
    assert attestation is not None, (
        "the clearance must ATTEST the declaration it cleared on -- a bare "
        "absence of a refusal is indistinguishable from 'never checked', and "
        "a bare word match against the commit output is not an attestation "
        "either (the E1 refusal's own HOW text mentions '@prefactoring'). "
        f"events={[e.get('event') for e in events]}, output={rendered[-1200:]!r}"
    )
    assert attestation.get("obligation") == "EXEMPT", (
        f"the attestation must carry the DECLARED obligation: {attestation!r}"
    )
    assert attestation.get("lane") == "prefactoring", (
        "the attestation must name the lane the obligation was read off, else "
        f"'EXEMPT' is a label with no antecedent: {attestation!r}"
    )


def test_undeclared_work_is_reported_indeterminate_and_still_commits(
    project: Path,
) -> None:
    """@driving_port @real-io

    THE THIRD STATE at the consuming surface, and DDD-5's ruling: loud and
    recorded, NOT blocking. Blocking here would refuse the measured 103/106
    code-touching commits that never went through a feature at all -- a cliff,
    not a gate.
    """
    # covers: R10
    _work_to_commit(project)

    _exit_code, events, rendered = _commit_outcome(project)

    assert event_named(events, ARMING_INDETERMINATE_EVENT) is not None, (
        "work with NO declaration must be reported LOUD as "
        f"{ARMING_INDETERMINATE_EVENT!r}; it was silent. "
        f"events={[e.get('event') for e in events]}, output={rendered[-1200:]!r}"
    )
    assert event_named(events, OBLIGATION_UNMET_EVENT) is None, (
        "INDETERMINATE is NON-BLOCKING (DDD-5) -- an undeclared commit must "
        f"not be refused as an unmet obligation. output={rendered[-1200:]!r}"
    )


def test_declared_exempt_and_never_declared_are_told_apart_at_the_commit(
    tmp_path: Path,
) -> None:
    """@driving_port @real-io

    THE DISCRIMINATOR, asserted as a DIFFERENCE rather than as two independent
    facts. `_examine_gate_armed` today gives both cases the SAME `False`; an AT
    that cannot tell them apart does not test the fix. Two projects, identical
    in every way except that one ran a dispatch, must produce observably
    different commit output.
    """
    # covers: R11
    declared = provision_project(tmp_path / "declared-exempt")
    undeclared = provision_project(tmp_path / "never-declared")
    dispatch(declared, SLICE_ID, lane="prefactoring")
    _work_to_commit(declared)
    _work_to_commit(undeclared)

    _d_exit, declared_events, declared_out = _commit_outcome(declared)
    _u_exit, undeclared_events, undeclared_out = _commit_outcome(undeclared)

    declared_names = {e.get("event") for e in declared_events}
    undeclared_names = {e.get("event") for e in undeclared_events}
    assert declared_names != undeclared_names or declared_out != undeclared_out, (
        "'declared EXEMPT' and 'never declared' produced IDENTICAL commit "
        "output -- the two-valued collapse survives. "
        f"events={sorted(map(str, declared_names))}"
    )
    assert ARMING_INDETERMINATE_EVENT in {str(n) for n in undeclared_names}, (
        "only the NEVER-DECLARED project may be reported INDETERMINATE; "
        f"undeclared events={sorted(map(str, undeclared_names))}"
    )
    assert ARMING_INDETERMINATE_EVENT not in {str(n) for n in declared_names}, (
        "the DECLARED-EXEMPT project was reported INDETERMINATE -- its "
        "declaration was thrown away"
    )


# ---------------------------------------------------------------------------
# OQ-6 blast radius -- the OTHER consumer of the widened arming result
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("lane", "must_report", "must_not_report"),
    [
        ("prefactoring", "EXEMPT", "INDETERMINATE"),
        (None, "INDETERMINATE", "EXEMPT"),
    ],
    ids=["declared-exempt", "never-declared"],
)
def test_the_completeness_verifier_keeps_exempt_and_indeterminate_distinct(
    project: Path, lane: str | None, must_report: str, must_not_report: str
) -> None:
    """@driving_port @real-io

    `check_examine_verdict` has THREE production callers, not one:
    `commit_slice.main:2189` plus `verify_slice_commit_completeness` at `:486`,
    `:1656`, `:1734`. Widening the arming result changes what the completeness
    verifier REPORTS too. Collapsing the two states there would reintroduce, in
    the verifier, exactly the flattening this feature removes from the gate.
    """
    # covers: R12
    if lane is not None:
        dispatch(project, SLICE_ID, lane=lane)
    _work_to_commit(project)

    _exit_code, stdout, stderr = verify_slice_commit_completeness(project, SLICE_ID)
    rendered = f"{stdout}\n{stderr}"

    assert must_report in rendered, (
        f"the completeness verifier must surface {must_report!r} for this "
        f"case; output={rendered[-1500:]!r}"
    )
    assert must_not_report not in rendered, (
        f"the completeness verifier reported {must_not_report!r} for the "
        f"{'declared-exempt' if lane else 'never-declared'} case -- the two "
        f"states are collapsed there; output={rendered[-1500:]!r}"
    )
