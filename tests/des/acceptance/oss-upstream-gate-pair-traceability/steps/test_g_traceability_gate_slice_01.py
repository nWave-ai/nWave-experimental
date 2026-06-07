"""pytest-bdd binding for the traceability-gate walking skeleton (slice-01).

Driving port: the production ``handle_subagent_stop`` SubagentStop hook, invoked
over its real JSON stdin protocol as a subprocess (Mandate-13 driving-port-only,
Layer 3/4 wiring_e2e). Step bodies delegate to the composition root
(``composition.py``); no production module is imported-and-called at the step
boundary, and no business logic lives in a step body (Mandate-12).

The ``scenarios(...)`` call binds every scenario in the ``.feature`` file. Each
step decorator's literal text is unique within this feature directory (S1
step-text-uniqueness invariant; this is the only step file in the directory).

RED scaffold: until DELIVER wires ``DecisionTableTraceabilityGate`` into the
``_handle_distill_exit_gate`` D_DISTILL branch, the hook emits no traceability
warning, so the Then-steps fail with a semantic ``AssertionError`` (never a
collection / import / setup error -- pre-DELIVER fail-for-right-reason gate).
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition import TraceabilityGateComposition


# Bind every scenario in the .feature through pytest-bdd's scenario machinery,
# using the RELATIVE path from this steps/ module -- IDENTICAL to the
# proven-collecting sibling suite
# (tests/des/acceptance/oss-hook-side-phase-injection/steps/test_g_distill_exit_gate.py:
# `scenarios("../g-distill-exit-gate.feature")`). This relative-string binding
# routes the scenario @tags (@slice-01, @driving_port, @real-io,
# @walking_skeleton, @contract-shape:*) through pytest-bdd's tag-to-dynamic-mark
# pipeline, which the project's filterwarnings makes --strict-markers-safe. An
# absolute resolved path (`scenarios(str(Path(...).resolve()))`) does NOT bind
# the same way and surfaced the tags as raw unregistered marks => collection
# error -- the empirical differential against the sibling.
scenarios("../g-traceability-gate-slice-01.feature")


@pytest.fixture
def composition() -> TraceabilityGateComposition:
    return TraceabilityGateComposition()


# --- Given -------------------------------------------------------------------


@given("a feature whose decision-table declares a clause with no witnessing test")
def given_clause_with_no_witnessing_test(
    composition: TraceabilityGateComposition,
) -> None:
    composition.given_clause_with_no_witnessing_test()


@given(
    "a feature whose decision-table declares one witnessed clause and one "
    "unwitnessed clause"
)
def given_one_witnessed_and_one_unwitnessed_clause(
    composition: TraceabilityGateComposition,
) -> None:
    composition.given_one_witnessed_and_one_unwitnessed_clause()


# --- When --------------------------------------------------------------------


@when("the acceptance designer returns and the DISTILL-exit gate evaluates the feature")
def when_distill_exit_gate_evaluates(
    composition: TraceabilityGateComposition,
) -> None:
    composition.when_distill_exit_gate_evaluates()


# --- Then --------------------------------------------------------------------


@then("the gate names the unwitnessed clause in its loud warning")
def then_names_unwitnessed_clause(composition: TraceabilityGateComposition) -> None:
    composition.then_names_unwitnessed_clause()


@then("the gate warns loudly about the unwitnessed clause")
def then_warns_about_unwitnessed_clause(
    composition: TraceabilityGateComposition,
) -> None:
    composition.then_warns_about_unwitnessed_clause()


@then("the gate stays silent about the witnessed clause")
def then_silent_about_witnessed_clause(
    composition: TraceabilityGateComposition,
) -> None:
    composition.then_silent_about_witnessed_clause()


@then("the gate lets the feature proceed to DELIVER")
def then_lets_feature_proceed(composition: TraceabilityGateComposition) -> None:
    composition.then_lets_feature_proceed()


@then("the hook exits with code zero")
def then_hook_exits_zero(composition: TraceabilityGateComposition) -> None:
    composition.then_hook_exits_zero()
