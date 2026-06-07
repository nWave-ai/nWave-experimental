"""Earned-verdict commit gate -- the slice-04 capstone decision (target-blind).

The commit gate is the end-to-end arm of the earned-verdict feature: it fires on
a ``git commit`` and rules whether the slice being committed is honest. For each
GREEN acceptance test in the slice it runs the perturb-loop -- a *baseline* run
(the AT as committed) and a *perturbed* run (the same AT with its declared
dependency broken at the seam) -- and rules a verdict through the SHIPPED
target-blind CORE (:func:`des.domain.earned_verdict.compute_verdict`). An AT whose
verdict is ``theater-held`` (RED) held green against broken code: the commit is
DENIED, naming the theater AT. An all-earned slice is ALLOWED.

This module is target-blind: it names no language and no test runner. It composes
the CORE over :class:`des.domain.earned_verdict.TestRun` pairs; the per-language
run + perturbation live in the shipped ``run_tests`` / ``inject_seam`` adapters,
behind the CORE. The gate consumes the slice's AT perturb-loop results and
applies the deterministic fail-safe rule: ABSTAIN never denies, RED always
denies, all-GREEN allows.
"""

from __future__ import annotations

from dataclasses import dataclass

from des.domain.earned_verdict import (
    EarnedVerdict,
    TestRun,
    VerdictStatus,
    compute_verdict,
)


@dataclass(frozen=True)
class AtPerturbation:
    """One acceptance test's baseline + perturbed runs, as the gate sees them.

    The gate rules a verdict per AT by passing this pair to the CORE. ``at_id``
    and ``seam_id`` echo onto the emitted verdict; ``baseline`` / ``perturbed``
    are the two real runs the perturb-loop produced for this AT.
    """

    at_id: str
    seam_id: str
    baseline: TestRun
    perturbed: TestRun


@dataclass(frozen=True)
class CommitGateDecision:
    """The gate's ruling on a ``git commit``.

    ``denied`` is the observable the PreToolUse hook maps onto
    ``permissionDecision:deny`` / ``{decision:block}``. ``reason`` names WHY --
    on a deny it names the theater AT so the operator knows which test held green
    against broken code, not merely that the commit was blocked.
    """

    denied: bool
    reason: str


def rule_commit(perturbations: tuple[AtPerturbation, ...]) -> CommitGateDecision:
    """Rule a commit by running the CORE over every AT's perturb-loop.

    Fail-safe: an ABSTAIN verdict never denies (the gate cannot make a
    trustworthy judgement, so it does not block). A theater-held RED verdict
    denies, naming the theater AT. An all-earned slice (every verdict GREEN, or
    GREEN-or-ABSTAIN) is allowed.
    """
    for perturbation in perturbations:
        verdict = _verdict_for(perturbation)
        if verdict.status is VerdictStatus.RED:
            return CommitGateDecision(denied=True, reason=_theater_reason(verdict))
    return CommitGateDecision(denied=False, reason="all acceptance tests are earned")


def _verdict_for(perturbation: AtPerturbation) -> EarnedVerdict:
    """Rule one AT's earned verdict through the shipped target-blind CORE."""
    return compute_verdict(
        perturbation.baseline,
        perturbation.perturbed,
        seam_id=perturbation.seam_id,
        at_id=perturbation.at_id,
    )


def _theater_reason(verdict: EarnedVerdict) -> str:
    """Name the theater AT on a deny so the operator knows WHICH test held green."""
    return (
        f"commit denied: acceptance test '{verdict.at_id}' is theater -- it held "
        f"green ({verdict.reason.value}) when its dependency was broken at seam "
        f"'{verdict.seam_id}'"
    )
