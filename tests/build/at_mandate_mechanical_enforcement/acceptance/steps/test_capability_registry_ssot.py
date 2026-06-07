"""Tier A step definitions — the adapter-capability-registry SSOT (slice-02).

CONTRACT_SHAPE: pure-function

Driving port: the real registry entrypoint
``des.testarch.capabilities.build_registry`` (the ``CapabilityRegistry`` catalog
+ ``check_conformance``), reached through the ``CapabilityRegistryService``
composition. Step bodies delegate to the service and assert against
port-exposed observables (the required-capability contract, the
``ConformanceOutcome`` enum, the named missing capability); no business logic is
inlined (Mandate-12 criterion 3).

Layer ~2 (in-memory query of the registry catalog, in-process) → example-based,
no PBT machinery (Mandate 9 v2: the only driven dependency is the in-memory
registry catalog; the contract is a finite enumerable set of 9 capabilities,
not an unbounded domain). The "catalog left unchanged" Then uses
``assert_state_delta`` over the port-observable required-capability set (Mandate
8: the universe is the contract the registry exposes, never an internal field).

Honest tagging: @component (auto-``unit`` under ``tests/build/``), NEVER
@wiring_e2e/@subprocess.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.capability_registry_composition import (
    build_service,
)
from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.domain_types import (
    EXPECTED_REQUIRED_CONTRACT,
    PLANTED_MISSING_CAPABILITY,
    ConformanceOutcome,
)
from tests.common.state_delta import assert_state_delta, unchanged


scenarios("../capability-registry-ssot.feature")


# --- fixtures --------------------------------------------------------------


@pytest.fixture
def service():
    """Production composition root for the capability-registry SSOT."""
    return build_service()


@pytest.fixture
def run_state() -> dict:
    """Mutable carrier for contract reads + verdicts across Given/When/Then."""
    return {}


# --- Given -----------------------------------------------------------------


@given("the adapter-capability registry")
def given_the_registry(service, run_state):
    # Precondition only — the registry service is the SUT entry. No expected
    # output is staged here (no Fixture Theater).
    run_state["service"] = service


# --- When ------------------------------------------------------------------


@when("the maintainer reads the required capabilities from the registry")
def when_read_required_capabilities(run_state):
    service = run_state["service"]
    run_state["before_contract"] = service.required_capabilities()
    run_state["required"] = service.required_capabilities()


@when(
    "the maintainer checks the reference language adapter against the capabilities the gates consume so far"
)
def when_check_reference_adapter(run_state):
    run_state["verdict"] = run_state["service"].check_reference_adapter()


@when("the maintainer checks a complete adapter against the full capability contract")
def when_check_complete_adapter(run_state):
    run_state["verdict"] = run_state["service"].check_complete_adapter()


@when("the maintainer checks an adapter that is missing a required capability")
def when_check_missing_capability_adapter(run_state):
    run_state["verdict"] = run_state["service"].check_missing_capability_adapter()


# --- Then ------------------------------------------------------------------


@then("the registry names the complete capability contract for a language adapter")
def then_names_complete_contract(run_state):
    assert run_state["required"] == EXPECTED_REQUIRED_CONTRACT


@then("every capability any registered gate-rule consumes is named in the contract")
def then_consumed_capabilities_contained(run_state):
    consumed = run_state["service"].consumed_capabilities()
    assert consumed <= run_state["required"]


@then("the registry catalog is left unchanged")
def then_catalog_unchanged(run_state):
    # Mandate 8: the universe is the port-observable required-capability contract.
    # Reading the SSOT is a pure-function query; the contract must be identical.
    after = run_state["service"].required_capabilities()
    assert_state_delta(
        before={"registry.required_capabilities": run_state["before_contract"]},
        after={"registry.required_capabilities": after},
        universe={"registry.required_capabilities"},
        expected={"registry.required_capabilities": unchanged()},
    )


@then("the registry reports the reference adapter as conformant")
def then_reference_conformant(run_state):
    outcome = run_state["service"].outcome_of(run_state["verdict"])
    assert outcome is ConformanceOutcome.CONFORMANT


@then("the registry names no missing capability for the reference adapter")
def then_reference_no_missing(run_state):
    assert run_state["verdict"].missing == ()


@then("the registry reports the adapter as non-conformant")
def then_adapter_non_conformant(run_state):
    outcome = run_state["service"].outcome_of(run_state["verdict"])
    assert outcome is ConformanceOutcome.NON_CONFORMANT


@then("the registry names the missing capability the implementer must still build")
def then_names_missing_capability(run_state):
    assert PLANTED_MISSING_CAPABILITY in run_state["verdict"].missing


@then("no gate-rule consumes a capability that the contract leaves out")
def then_no_gate_consumes_unlisted_capability(run_state):
    # SSOT honesty (fail-closed): every capability any registered rule consumes
    # must be named in the contract. If a gate could depend on an unlisted
    # capability, the registry would not be the single checklist it claims.
    consumed = run_state["service"].consumed_capabilities()
    assert consumed <= run_state["required"]
