"""Target-blind earned-verdict CORE (ADR-042 Earned-Verdict, OSS hook tier).

The CORE is the pure, deterministic heart of the earned-verdict gate. It
consumes TWO ``nwave.test_result.v1`` envelopes -- a *baseline* run and a
*perturbed* run (the same acceptance test re-run with its declared dependency
broken at the seam) -- and rules whether the baseline green was EARNED
(causally bound to the thing it asserts) or merely held against broken code.

The verdict is computed by the frozen deterministic rule, NEVER by an LLM:

    GREEN    baseline.passed > 0 AND baseline.failed == 0
             AND (perturbed.failed > 0 OR perturbed.exit_code != 0)
             -- the run flipped when its dependency broke: honest.
             reason = verdict-flipped
    RED      baseline green AND perturbed STILL green
             -- the run survived broken code: theater.
             reason = theater-held
    ABSTAIN  baseline NOT green (failed > 0 OR passed == 0)
             -- there is no honest green to perturb: fail-safe.
             reason = baseline-not-green

target-blind invariant: the CORE names NO language and NO test runner. It
branches only on the contract fields ``passed`` / ``failed`` / ``exit_code``.
The ``runner`` field of ``nwave.test_result.v1`` rides through opaquely -- the
verdict is identical for any runner string. ``seam_id`` and ``at_id`` are
echoed verbatim from the inputs onto the emitted ``nwave.earned_verdict.v1``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import cast


TEST_RESULT_SCHEMA = "nwave.test_result.v1"
EARNED_VERDICT_SCHEMA = "nwave.earned_verdict.v1"


class VerdictStatus(str, Enum):
    """The frozen ``status`` closed enum of ``nwave.earned_verdict.v1``."""

    GREEN = "GREEN"
    RED = "RED"
    ABSTAIN = "ABSTAIN"


class VerdictReason(str, Enum):
    """The frozen ``reason`` closed enum of ``nwave.earned_verdict.v1``."""

    VERDICT_FLIPPED = "verdict-flipped"
    THEATER_HELD = "theater-held"
    BASELINE_NOT_GREEN = "baseline-not-green"


@dataclass(frozen=True)
class TestRun:
    """One ``nwave.test_result.v1`` run, as the CORE reads it.

    Only ``passed`` / ``failed`` / ``exit_code`` drive the verdict; ``runner``
    rides opaquely (the CORE never branches on it). The CORE consumes a TestRun
    rather than a raw dict so the deterministic rule reads intention-revealing
    fields, not contract-string lookups.
    """

    runner: str
    passed: int
    failed: int
    exit_code: int

    def is_green(self) -> bool:
        """Whether this run is a healthy green: something passed, nothing failed."""
        return self.passed > 0 and self.failed == 0

    def flipped(self) -> bool:
        """Whether this run broke: a counted failure OR a nonzero process exit."""
        return self.failed > 0 or self.exit_code != 0


@dataclass(frozen=True)
class EarnedVerdict:
    """The CORE's output: a ``nwave.earned_verdict.v1`` datum.

    ``seam_id`` and ``at_id`` echo verbatim the identifiers the CORE was asked
    about. ``baseline`` and ``perturbed`` are the two embedded
    ``nwave.test_result.v1`` sub-envelopes, carried through unchanged.
    """

    status: VerdictStatus
    reason: VerdictReason
    seam_id: str
    at_id: str
    baseline: TestRun
    perturbed: TestRun


def compute_verdict(
    baseline: TestRun,
    perturbed: TestRun,
    seam_id: str,
    at_id: str,
) -> EarnedVerdict:
    """Rule whether a baseline green was EARNED, per the frozen deterministic rule.

    Fail-safe first: a baseline that is not green has no honest green to
    perturb, so the CORE abstains before ever inspecting the perturbed run. A
    green baseline then earns its verdict by whether the perturbed run flipped.
    """
    if not baseline.is_green():
        return _verdict(
            VerdictStatus.ABSTAIN,
            VerdictReason.BASELINE_NOT_GREEN,
            baseline,
            perturbed,
            seam_id,
            at_id,
        )
    if perturbed.flipped():
        return _verdict(
            VerdictStatus.GREEN,
            VerdictReason.VERDICT_FLIPPED,
            baseline,
            perturbed,
            seam_id,
            at_id,
        )
    return _verdict(
        VerdictStatus.RED,
        VerdictReason.THEATER_HELD,
        baseline,
        perturbed,
        seam_id,
        at_id,
    )


def _verdict(
    status: VerdictStatus,
    reason: VerdictReason,
    baseline: TestRun,
    perturbed: TestRun,
    seam_id: str,
    at_id: str,
) -> EarnedVerdict:
    """Assemble an ``EarnedVerdict``, echoing seam/node verbatim from the inputs."""
    return EarnedVerdict(
        status=status,
        reason=reason,
        seam_id=seam_id,
        at_id=at_id,
        baseline=baseline,
        perturbed=perturbed,
    )


def test_run_from_envelope(envelope: dict[str, object]) -> TestRun:
    """Read a ``nwave.test_result.v1`` envelope into a TestRun.

    The CORE consumes only the verdict-relevant fields (``runner``, ``passed``,
    ``failed``, ``exit_code``). Malformed-input handling (a wrong-schema or
    partial envelope) is owned residue R-1, deferred to slice-02 where the
    TestRunnerPort first makes a malformed run reachable; slice-01 feeds only
    well-formed envelopes, so this read is total over the inputs it sees.
    """
    return TestRun(
        runner=str(envelope["runner"]),
        passed=_count(envelope["passed"]),
        failed=_count(envelope["failed"]),
        exit_code=_count(envelope["exit_code"]),
    )


def _count(value: object) -> int:
    """Read a frozen-contract integer field from a JSON-parsed envelope value."""
    return int(cast("int", value))


def _test_result_envelope(run: TestRun) -> dict[str, object]:
    """Re-emit a TestRun as a ``nwave.test_result.v1`` sub-envelope.

    Only the verdict-relevant fields carry the run's intent; the remaining
    frozen fields take neutral zero defaults so the embedded sub-envelope is a
    complete, schema-valid ``nwave.test_result.v1``.
    """
    return {
        "schema": TEST_RESULT_SCHEMA,
        "runner": run.runner,
        "exit_code": run.exit_code,
        "collected": run.passed + run.failed,
        "passed": run.passed,
        "failed": run.failed,
        "xfailed": 0,
        "xpassed": 0,
        "skipped": 0,
        "deselected": 0,
        "error": 0,
    }


def earned_verdict_envelope(verdict: EarnedVerdict) -> dict[str, object]:
    """Serialise an ``EarnedVerdict`` as a ``nwave.earned_verdict.v1`` envelope."""
    return {
        "schema": EARNED_VERDICT_SCHEMA,
        "status": verdict.status.value,
        "seam_id": verdict.seam_id,
        "at_id": verdict.at_id,
        "baseline": _test_result_envelope(verdict.baseline),
        "perturbed": _test_result_envelope(verdict.perturbed),
        "reason": verdict.reason.value,
    }
