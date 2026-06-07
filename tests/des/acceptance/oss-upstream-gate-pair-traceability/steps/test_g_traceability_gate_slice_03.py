"""pytest-bdd binding for the behavioral witness-check slice (slice-03).

Driving port: the production ``handle_subagent_stop`` SubagentStop hook over its
real JSON stdin protocol as a subprocess (Mandate-13 driving-port-only, Layer 3/4
wiring_e2e) -- identical surface to slice-01/02. Step bodies delegate to the
slice-03 composition root (``composition_slice_03.py``, a subclass of the slice-01
``TraceabilityGateComposition`` that REUSES the ``when`` + signed-verdict seed and
adds the three behaviorally-rich slice-03 ``Given`` + ``Then`` methods). No
production gate / port / adapter module is imported-and-called at the step
boundary; no business logic lives in a step body (Mandate-12).

STEP-REGISTRY SCOPE (S1 step-text uniqueness): pytest-bdd resolves step
decorators per binding-module via this file's ``scenarios(...)`` call. This module
owns its own step registry; its ``Given``/``Then`` literals are NEW (they speak
the slice-03 witness vocabulary, not slice-01/02's syntactic-join vocabulary) and
do not collide with the sibling slice modules. The shared ``When`` literal
("the acceptance designer returns ...") is RE-DECLARED here against the slice-03
composition so this module's registry is self-contained -- pytest-bdd keys step
bodies per binding-module, so the same literal in three modules is three
independent registrations, never a shadow (S1 tolerable-variant: per-module
registry isolation). Verified by the mandatory --co proof: slice-01 (3) +
slice-02 (2) + slice-03 (3) all collect EXIT=0 under the canonical
--strict-markers addopts.

RED scaffold (ADR-025 + ADR-028): the ``ClauseWitnessPort`` /
``PerturbationWitnessAdapter`` do not exist yet and the shipped slice-01 gate is
purely SYNTACTIC -- it stays silent about every name-matched clause. Each
slice-03 ``Then`` asserts the gate DOWNGRADES a name-matched-but-vacuous /
unresolved clause, which fails with a semantic ``AssertionError`` (no such
warning on the gate's stderr) -- never a collection / import / setup error
(pre-DELIVER fail-for-right-reason gate). They PASS once DELIVER slice-03 wires
the behavioral witness-check into the D_DISTILL branch.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_03 import TraceabilityWitnessComposition


# Relative-string binding -- IDENTICAL pattern to slice-01/02 (proven to route
# the scenario @tags through pytest-bdd's strict-markers-safe dynamic-mark
# pipeline).
scenarios("../g-traceability-gate-slice-03.feature")


@pytest.fixture
def composition() -> TraceabilityWitnessComposition:
    return TraceabilityWitnessComposition()


# --- Given (NEW slice-03 behavioral substrate) -------------------------------


@given(
    "a feature with one test that asserts its target's outcome and two tests "
    "that exercise the target without asserting its outcome"
)
def given_genuine_and_two_non_asserting_clauses(
    composition: TraceabilityWitnessComposition,
) -> None:
    composition.given_genuine_and_two_non_asserting_clauses()


@given("a feature whose clause is checked against a real production source file")
def given_clause_checked_against_real_source(
    composition: TraceabilityWitnessComposition,
) -> None:
    composition.given_clause_checked_against_real_source()


@given(
    "a feature whose clause names a production target that does not exist in "
    "the source tree"
)
def given_clause_with_unresolvable_target(
    composition: TraceabilityWitnessComposition,
) -> None:
    composition.given_clause_with_unresolvable_target()


# --- When (REUSED slice-01 vocabulary, re-bound to slice-03 composition) ------


@when("the acceptance designer returns and the DISTILL-exit gate evaluates the feature")
def when_distill_exit_gate_evaluates(
    composition: TraceabilityWitnessComposition,
) -> None:
    composition.when_distill_exit_gate_evaluates()


# --- Then (NEW slice-03 behavioral outcomes) ---------------------------------


@then("the gate stays silent about the test that asserts its target's outcome")
def then_silent_about_genuine_clause(
    composition: TraceabilityWitnessComposition,
) -> None:
    composition.then_silent_about_genuine_clause()


@then(
    "the gate surfaces both tests that exercise but do not assert their target "
    "as unwitnessed"
)
def then_surfaces_both_non_asserting_clauses(
    composition: TraceabilityWitnessComposition,
) -> None:
    composition.then_surfaces_both_non_asserting_clauses()


@then("the real production source file is byte-identical after the witness-check")
def then_real_source_byte_identical(
    composition: TraceabilityWitnessComposition,
) -> None:
    composition.then_real_source_byte_identical()


@then("the witness-check uses no version-control to undo its perturbation")
def then_no_version_control_used(
    composition: TraceabilityWitnessComposition,
) -> None:
    composition.then_no_version_control_used()


@then(
    "the gate surfaces the clause as unwitnessed because its target cannot be located"
)
def then_surfaces_unresolved_target(
    composition: TraceabilityWitnessComposition,
) -> None:
    composition.then_surfaces_unresolved_target()
