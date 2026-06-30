"""pytest-bdd binding for f-rust-test-runner-adapter slice-03 scenarios.

Driving surface (Mandate-13 driving-port-only, Layer 3 subprocess): the REAL
operator-facing contract gate ``python -m des.cli.run_contract_gate --feature-id``
run as a subprocess over a GENUINE controlled Cargo target + a FAKE-cargo
executable -- the EXACT subprocess ``verify_slice_commit_completeness`` composes
for E2. Step bodies delegate to the composition root
(``composition_slice_03_e2_routing.py``); no business logic in step bodies
(Mandate-12 criterion 3). The verdict + runner.json presence are parsed into the
typed ``GateOutcome`` / ``RunnerJsonPresence`` enums (DSL emergence, not decorator
proliferation).

ZERO ``des.*`` import in THIS process: the SUT is the contract-gate CLI, exercised
ONLY across the subprocess boundary inside the composition root's child run.

Active-RED scaffold (atdd_pure -- NOT @skip): RED until DELIVER ships the three
slice-03 wiring points (the ``_mode_feature_scoped`` runner-resolution
short-circuit, the registry dispatch in ``RunnerAdapter.run``, and the
``runner_json.py`` reader). At HEAD the gate runs the pytest-bound collection
worker on the Cargo target -> ``FeatureScopeMalformed / zero-collected`` (and the
fake cargo is never invoked), so each Then fails with a semantic AssertionError,
never a collection / import error.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_03_e2_routing import E2RoutingComposition
from .domain_types_e2_routing import GateOutcome


scenarios("../slice-03-e2-routing.feature")


@pytest.fixture
def e2() -> E2RoutingComposition:
    return E2RoutingComposition()


# --- Given -----------------------------------------------------------------


@given("a convention-following Rust target shipping no runner.json")
def given_convention_no_runner_json(e2: E2RoutingComposition) -> None:
    e2.given_convention_following_rust_target_no_runner_json()


@given("a Rust target shipping a runner.json override")
def given_runner_json_override(e2: E2RoutingComposition) -> None:
    e2.given_convention_following_rust_target_with_runner_json_override()


# --- When ------------------------------------------------------------------


@when("the operator runs the feature-scoped contract gate")
def when_operator_runs_gate(e2: E2RoutingComposition) -> None:
    e2.when_the_operator_runs_the_feature_scoped_gate()


# --- Then ------------------------------------------------------------------


@then("the gate clears the feature scope through cargo")
def then_gate_clears_through_cargo(e2: E2RoutingComposition) -> None:
    e2.then_the_gate_outcome_is(GateOutcome.CLEARED)


@then("the gate drove the convention-derived binary selector")
def then_gate_drove_convention_selector(e2: E2RoutingComposition) -> None:
    e2.then_the_gate_drove_the_convention_derived_selector()


@then("the gate drove the runner.json override command")
def then_gate_drove_override(e2: E2RoutingComposition) -> None:
    e2.then_the_gate_drove_the_runner_json_override()


@then("the gate does not emit a pytest collection failure")
def then_gate_no_pytest_collection_failure(e2: E2RoutingComposition) -> None:
    e2.then_the_gate_does_not_emit_a_pytest_collection_failure()
