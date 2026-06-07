"""Tier A step definitions — the dispatcher registration-contract gate
(slice-06).

CONTRACT_SHAPE: pure-function

Driving port: the real rule entrypoint
``des.testarch.rules.registration_contract.check_registry``, reached through the
``RegistrationContractGate`` composition service. Step bodies delegate to the
service and assert against port-exposed observables (the ``RegistrationOutcome``
enum, the named offending rows, the checked row count); no business logic is
inlined (Mandate-12 criterion 3).

Layer ~2 (in-process importlib resolution) → example-based, no PBT machinery
(Mandate 9 v2: the only driven dependency is the in-process importlib resolution
of registry rows, so the OR-reduction keeps it example-based here — the registry
corpora are finite and enumerable, not an unbounded domain). The "left
untouched" Then uses ``assert_state_delta`` over the inspected registry's
port-observable row names (Mandate 8: the universe is the registry's observable
row names, never an internal rule field).

Honest tagging: @component (auto-``unit`` under ``tests/build/``), NEVER
@wiring_e2e/@subprocess — the gate practises the honesty it enforces.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.domain_types import (
    EXPECTED_MAIN_MISSING_ROW,
    EXPECTED_UNIMPORTABLE_ROW,
    RegistrationOutcome,
    RegistryCorpusKind,
)
from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.registration_contract_composition import (
    build_gate,
)
from tests.common.state_delta import assert_state_delta, unchanged


scenarios("../registration-contract-gate.feature")


# --- fixtures --------------------------------------------------------------


@pytest.fixture
def gate():
    """Production composition root for the registration-contract gate."""
    return build_gate()


@pytest.fixture
def run_state() -> dict:
    """Mutable carrier for verdicts + snapshots across Given/When/Then."""
    return {}


# --- helpers ---------------------------------------------------------------


def _row_names(registry) -> tuple[str, ...]:
    """The port-observable row names of a registry (order-preserving)."""
    return tuple(row.name for row in registry)


# --- Given -----------------------------------------------------------------


@given("the dispatcher registration-contract gate")
def given_the_gate(gate, run_state):
    # Precondition only — the gate object is the SUT entry. No expected output
    # is staged here (no Fixture Theater).
    run_state["gate"] = gate


# --- When ------------------------------------------------------------------


@when("the gate checks a registry with a dropped module and a missing entry")
def when_check_dropped_or_broken(run_state):
    gate = run_state["gate"]
    run_state["corpus"] = RegistryCorpusKind.DROPPED_OR_BROKEN
    run_state["snapshot_row_names"] = _row_names(
        gate.registry_for(RegistryCorpusKind.DROPPED_OR_BROKEN)
    )
    run_state["verdict"] = gate.inspect(RegistryCorpusKind.DROPPED_OR_BROKEN)


@when("the gate checks a registry whose every row resolves and exposes its entry")
def when_check_fully_wired(run_state):
    gate = run_state["gate"]
    run_state["verdict"] = gate.inspect(RegistryCorpusKind.FULLY_WIRED)


@when("the gate checks the live dispatcher registry read at runtime")
def when_check_live(run_state):
    gate = run_state["gate"]
    run_state["live_row_count"] = len(gate.registry_for(RegistryCorpusKind.LIVE))
    run_state["verdict"] = gate.inspect(RegistryCorpusKind.LIVE)


# --- Then ------------------------------------------------------------------


@then("the registration-contract gate rules the registry non-conformant")
def then_flagged(run_state):
    outcome = run_state["gate"].outcome_of(run_state["verdict"])
    assert outcome is RegistrationOutcome.FLAGGED


@then("the gate names the dropped-module row and the missing-entry row")
def then_names_breaches(run_state):
    named = {breach.row_name for breach in run_state["verdict"].breaches}
    assert {
        str(EXPECTED_UNIMPORTABLE_ROW),
        str(EXPECTED_MAIN_MISSING_ROW),
    } <= named


@then("the inspected registry is left untouched")
def then_registry_untouched(run_state):
    # Mandate 8: the universe is the port-observable row names of the inspected
    # registry. The gate is a pure read; the registry's rows must be unchanged.
    after_names = _row_names(run_state["gate"].registry_for(run_state["corpus"]))
    assert_state_delta(
        before={"registry.row_names": run_state["snapshot_row_names"]},
        after={"registry.row_names": after_names},
        universe={"registry.row_names"},
        expected={"registry.row_names": unchanged()},
    )


@then("the registration-contract gate rules the registry conformant")
def then_conformant(run_state):
    outcome = run_state["gate"].outcome_of(run_state["verdict"])
    assert outcome is RegistrationOutcome.CONFORMANT


@then("the gate raises no objection to the fully-wired registry")
def then_no_false_positive(run_state):
    # Precision half: every row of the clean fixture resolves, imports, and
    # exposes a callable main — the gate must report zero breaches.
    assert run_state["verdict"].breaches == ()


@then("the gate checked every row the live registry exposes")
def then_count_agnostic(run_state):
    # Count-agnostic / auto-extend half: the gate scaled to the live registry's
    # full size with no per-subcommand authoring. The port-observable row_count
    # equals the live registry's length read independently — so a newly-added
    # valid subcommand row is auto-covered.
    assert run_state["verdict"].row_count == run_state["live_row_count"]
    assert run_state["live_row_count"] >= 1
