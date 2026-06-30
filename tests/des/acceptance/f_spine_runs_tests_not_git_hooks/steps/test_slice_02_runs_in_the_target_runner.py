"""pytest-bdd binding for f-spine-runs-tests-not-git-hooks slice-02.

The AGNOSTIC RUN + the NA guard. The SUT is the same NEW in-tree executor
``des.cli.run_slice_ats`` (slice-01), now exercised across target manifests so
``TestRunnerPort.resolve`` is consulted FIRST (HIGH-2 short-circuit) and an
unrecognized target degrades LOUD to INDETERMINATE (never a silent pytest
fallback), and a no-real-AT slice returns NOT_APPLICABLE (HIGH-1, no fabricated
always-green AT). Step bodies delegate to the shared composition root; no business
logic in step bodies (Mandate-12). HERMETIC: tmp workspaces only, no developer
home read.

Driving surface (Mandate-13, Layer-3 subprocess): ``python -m des.cli.run_slice_ats``
with ``--repo-root`` / ``--entering-slice``. observable = exit code (PASS=0 /
INDETERMINATE != {0,1} / NOT_APPLICABLE=0) + the JSON line {verdict, runner, reason}.

S1 (step-text uniqueness): the shared verbs ("a developer commits the entering
slice", "the spine slice-AT gate runs") live ONCE in conftest. This module's
unique verbs (runner resolution, no-real-AT, indeterminate/not-applicable Thens)
do not recur in slice-01's module -- no cross-module shadow. "the entering slice
has a green acceptance test" is reused from slice-01 via the explicit import of
the slice-01 step function (single-source, no shadow -- the S1 tolerable-variant).

Active-RED scaffold (atdd_pure -- NOT @skip): RED until slice-02's DELIVER ships
the resolve()-first executor path + the no-real-AT NOT_APPLICABLE guard + the
Indeterminate->INDETERMINATE mapping. At HEAD the executor module is absent, so
the subprocess exits non-zero (NEITHER PASS=0 nor a typed INDETERMINATE/NA shape)
-> semantic AssertionErrors against the expected verdict.
"""

from __future__ import annotations

from pytest_bdd import given, parsers, scenarios, then

from .composition import SliceRunComposition, spine  # noqa: F401
from .domain_types import SliceVerdict, TargetRunner


# "the entering slice has a green acceptance test" is the SHARED SSOT verb,
# declared once in conftest.py (used by slice-01 + slice-02). pytest-bdd resolves
# it from the conftest step registry for THIS module's scenarios -- no import, no
# cross-module shadow (S1 tolerable-variant: single-source shared step).


scenarios("../slice-02-runs-in-the-target-runner.feature")


# --- Given (slice-02 unique) -----------------------------------------------


@given(parsers.parse('the target project resolves to the "{runner}" runner'))
def given_target_resolves_runner(spine: SliceRunComposition, runner: str) -> None:
    spine.given_target_runner(TargetRunner(runner))


@given("the target project resolves to no recognized runner")
def given_target_resolves_nothing(spine: SliceRunComposition) -> None:
    spine.given_target_runner(TargetRunner.ABSENT)


@given("the entering slice has no real acceptance test")
def given_no_real_slice_at(spine: SliceRunComposition) -> None:
    spine.given_no_planted_slice_at()


# --- Then (slice-02 unique) ------------------------------------------------


@then(parsers.parse('the slice tests ran in the resolved "{runner}" runner'))
def then_ran_in_resolved_runner(spine: SliceRunComposition, runner: str) -> None:
    spine.then_runner_resolved_is(TargetRunner(runner))


@then("the spine slice-AT gate reports indeterminate")
def then_gate_indeterminate(spine: SliceRunComposition) -> None:
    spine.then_verdict_is(SliceVerdict.INDETERMINATE)


@then("the indeterminate reason names the unresolved runner")
def then_indeterminate_reason_named(spine: SliceRunComposition) -> None:
    spine.then_degrade_loud_reason_named()


@then("the spine slice-AT gate reports not-applicable")
def then_gate_not_applicable(spine: SliceRunComposition) -> None:
    spine.then_verdict_is(SliceVerdict.NOT_APPLICABLE)
