"""Tier A step definitions — the drift-guard conformance gate (slice-12).

CONTRACT_SHAPE: pure-function

Driving port: the parametrized conformance-rule entrypoints
``detect_layer_value_coverage`` + ``detect_real_adapter_capability_conformance``
(``des.testarch.rules.registry_conformance``), reached through the
``RegistryConformanceService`` composition. Step bodies delegate to the service and
assert against port-exposed observables (the ``ConformanceOutcomeKind`` enum, the
named offenders); no business logic is inlined (Mandate-12 criterion 3).

Recall/precision golden-fixture shape (ADR-TEST-002 D-E):

  * RECALL scenario — drives the detectors against the FROZEN drifted snapshot
    (which permanently carries both drift facets). Asserts FLAGGED + the named
    planted offenders. Green forever (the live substrate is cleaned by A_GREEN; the
    frozen fixture is never cleaned).
  * PRECISION scenario — drives the detectors against the LIVE production surface
    read at runtime. Asserts CONFORMANT (zero violations). RED NOW (the live
    substrate carries fs_acceptance + the dead caps); GREEN after A_GREEN drops
    them. THIS is the scenario the drops flip RED->GREEN.

Layer ~2 (in-memory introspection of the testarch substrate, in-process) →
example-based, no PBT machinery (Mandate 9 v2: the only driven dependency is the
in-memory testarch package surface; the conformance fact is a finite enumerable
cross-check, not an unbounded domain). The conformance reads are pure-function
queries that mutate no state — the verdict is the port-exposed observable, so the
Then steps assert directly on it (no ``assert_state_delta`` universe to declare;
nothing is mutated — Mandate-8 layer-1-3 universe-guard applies to STATE-MUTATING
steps only).

RED-for-right-reason (ADR-025 / Mandate-7): both When steps drive the production
``detect_*`` functions, which are RED scaffolds raising ``AssertionError`` until
A_GREEN implements them. The recall scenario goes GREEN when the detectors are
implemented; the precision scenario goes GREEN when the detectors are implemented
AND the live drift is cleaned. The failures are semantic ``AssertionError`` against
the missing conformance behaviour — NOT collection / import / skip errors.

Honest tagging: @component (auto-``unit`` under ``tests/build/``), NEVER
@wiring_e2e/@subprocess.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from tests.build.at_mandate_mechanical_enforcement.acceptance.fixtures.registry_conformance.violation_drifted_snapshot import (
    PLANTED_NON_PRODUCIBLE_LAYER_VALUE,
    PLANTED_UNREALIZED_CAPABILITY,
)
from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.domain_types import (
    ConformanceOutcomeKind,
)
from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.registry_conformance_composition import (
    build_service,
)


scenarios("../registry-conformance-gate.feature")


# --- fixtures --------------------------------------------------------------


@pytest.fixture
def service():
    """Production composition root for the drift-guard conformance gate."""
    return build_service()


@pytest.fixture
def run_state() -> dict:
    """Mutable carrier for the layer + capability verdicts across Given/When/Then."""
    return {}


# --- Given -----------------------------------------------------------------


@given("the testarch drift-guard conformance gate")
def given_the_conformance_gate(service, run_state):
    # Precondition only — the conformance service is the SUT entry. No expected
    # output is staged here (no Fixture Theater).
    run_state["service"] = service


# --- When ------------------------------------------------------------------


@when("the maintainer checks the frozen drifted snapshot")
def when_check_drifted_snapshot(run_state):
    service = run_state["service"]
    run_state["layer_verdict"] = service.layer_value_coverage_of_drifted_snapshot()
    run_state["capability_verdict"] = (
        service.capability_conformance_of_drifted_snapshot()
    )


@when("the maintainer checks the frozen conformant snapshot")
def when_check_clean_snapshot(run_state):
    service = run_state["service"]
    run_state["layer_verdict"] = service.layer_value_coverage_of_clean_snapshot()
    run_state["capability_verdict"] = service.capability_conformance_of_clean_snapshot()


@when("the maintainer checks the live testarch substrate")
def when_check_live_substrate(run_state):
    service = run_state["service"]
    run_state["layer_verdict"] = service.layer_value_coverage_of_live_substrate()
    run_state["capability_verdict"] = service.capability_conformance_of_live_substrate()


# --- Then (recall) ---------------------------------------------------------


@then("the gate flags the layer-value drift in the snapshot")
def then_flags_snapshot_layer_drift(run_state):
    outcome = run_state["service"].layer_outcome_of(run_state["layer_verdict"])
    assert outcome is ConformanceOutcomeKind.FLAGGED


@then("the gate names the non-producible layer value the snapshot references")
def then_names_snapshot_non_producible_layer(run_state):
    named = {
        violation.layer_value for violation in run_state["layer_verdict"].violations
    }
    assert PLANTED_NON_PRODUCIBLE_LAYER_VALUE in named


@then("the gate flags the capability drift in the snapshot")
def then_flags_snapshot_capability_drift(run_state):
    outcome = run_state["service"].capability_outcome_of(
        run_state["capability_verdict"]
    )
    assert outcome is ConformanceOutcomeKind.FLAGGED


@then("the gate names the registered capability the snapshot adapter does not realize")
def then_names_snapshot_unrealized_capability(run_state):
    named = {
        violation.capability for violation in run_state["capability_verdict"].violations
    }
    assert PLANTED_UNREALIZED_CAPABILITY in named


# --- Then (precision) ------------------------------------------------------


@then("the gate reports every rule-referenced layer value as adapter-producible")
def then_live_layer_conformant(run_state):
    outcome = run_state["service"].layer_outcome_of(run_state["layer_verdict"])
    assert outcome is ConformanceOutcomeKind.CONFORMANT


@then("the gate reports every registered capability as realized on the real adapter")
def then_live_capability_conformant(run_state):
    outcome = run_state["service"].capability_outcome_of(
        run_state["capability_verdict"]
    )
    assert outcome is ConformanceOutcomeKind.CONFORMANT
