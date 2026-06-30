"""pytest-bdd binding for f-spine-runs-tests-not-git-hooks slice-04.

CERTAINTY made mechanical (CT-7 -- the feature-end full-suite certainty the
git-hook-removal is gated on). The SUT is the REAL feature-end full-suite leg
(``des.cli.run_contract_gate`` default whole-tree mode -- the subprocess the
``feature_end_cycle_service`` full-suite leg invokes ONCE at feature-end). Drives
it via ``python -m des.cli.run_contract_gate --repo <tmp>`` over a tmp repo whose
planted contract suite is green vs RED, and asserts the leg's observable: a green
suite exits 0 (the cycle would emit ``FullSuiteLegRan``); a PRESENT-but-RED suite
exits non-zero (the cycle -> ``CycleRefusal``, NO record -- anti-theater).

Step bodies delegate to the shared composition root; no business logic in step
bodies (Mandate-12). HERMETIC: tmp repos only, no developer-home read. Driving
surface (Mandate-13, Layer-3 subprocess): ``python -m des.cli.run_contract_gate
--repo <tmp>``. observable = the full-suite leg's exit code (green->0 / red->!=0).

The companion arch ATs (tests/build/f_spine_runs_tests_not_git_hooks/
test_arch_run_slice_ats_wired.py = AT-A1, test_arch_feature_end_full_suite_required.py
= CT-7-coherence) and the integration veto-probe (tests/des/integration/
test_spine_slice_at_veto_no_git_hook.py = AT-A5) are NOT pytest-bdd scenarios
(not counted toward the carpaccio ceiling); they witness the WIRING seam + the
no-git-hook veto self-application.

S1 (step-text uniqueness): this module's verbs ("a feature-end cycle over a
repository whose full suite is green/red", "the feature-end cycle runs the full
suite once", the leg-record Thens) are UNIQUE to slice-04 -- they do not recur in
slice-01/02/03's modules.

Active-RED scaffold (atdd_pure -- NOT @skip): the CT-7 leg is REUSED from
f-nonbypassable-attestation (already built), so the green/red exit-code contract
already holds for the leg. slice-04's RED at HEAD is carried by the companion
arch AT (AT-A1: the `run-slice-ats` subcommand row is absent -> the executor is
unwired dead code) + the integration veto-probe (the executor module is absent).
These Gherkin CT-7 scenarios pin the feature-end-certainty contract the
git-hook-removal is gated on -- a tested property, not a claim.
"""

from __future__ import annotations

from pytest_bdd import given, scenarios, then, when

from .composition import FeatureEndCertaintyComposition, feature_end  # noqa: F401
from .domain_types import SliceAtColour


scenarios("../slice-04-certainty-made-mechanical.feature")


# --- Given (slice-04) ------------------------------------------------------


@given("a feature-end cycle over a repository whose full suite is green")
def given_green_full_suite(feature_end: FeatureEndCertaintyComposition) -> None:
    feature_end.given_full_suite(SliceAtColour.GREEN)


@given("a feature-end cycle over a repository whose full suite is red")
def given_red_full_suite(feature_end: FeatureEndCertaintyComposition) -> None:
    feature_end.given_full_suite(SliceAtColour.RED)


# --- When (slice-04) -------------------------------------------------------


@when("the feature-end cycle runs the full suite once")
def when_full_suite_runs(feature_end: FeatureEndCertaintyComposition) -> None:
    feature_end.when_full_suite_leg_runs()


# --- Then (slice-04) -------------------------------------------------------


@then("the full-suite leg record attests the green run")
def then_leg_attests_green(feature_end: FeatureEndCertaintyComposition) -> None:
    feature_end.then_full_suite_leg_attested()


@then("the feature-end cycle is refused with no full-suite leg record")
def then_cycle_refused_no_record(
    feature_end: FeatureEndCertaintyComposition,
) -> None:
    feature_end.then_cycle_refused_no_record()
