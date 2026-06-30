"""pytest-bdd binding for f-wave-contract-coherence slice-02 (coherence-check gate).

Driving surface (Mandate-13 driving-port-only): the REAL
``des verify-wave-contract-coherence`` subcommand invoked as a Layer-3 subprocess
through the shipped ``des`` dispatcher (composition_coherence_check.py). Step bodies
delegate to the composition root; no business logic in step bodies (Mandate-12).

Active-RED scaffold (atdd_pure -- NOT @skip): each scenario is RED until DELIVER
ships ``src/des/cli/verify_wave_contract_coherence.py`` + its ``_REGISTRY`` row +
``_catalog.yaml`` mirror. At HEAD the subcommand does not exist, so the gate emits
no verdict token -> every Then fires a semantic AssertionError naming the missing
gate subcommand, never a collection / import / setup error.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_coherence_check import CoherenceCheckComposition
from .domain_types import CoherenceVerdict


scenarios("../coherence-check-gate.feature")


@pytest.fixture
def gate(tmp_path: Path) -> CoherenceCheckComposition:
    return CoherenceCheckComposition(tmp_path=tmp_path)


# --- Given -----------------------------------------------------------------


@given("a wave-contract registry entry for the DISCUSS wave carrying both SSOTs")
def given_registry_entry_for_discuss_with_both_ssots(
    gate: CoherenceCheckComposition,
) -> None:
    gate.given_registry_entry_for_discuss_with_both_ssots()


@given("the wave-contract registry the gate must read is unreadable")
def given_registry_is_unreadable(gate: CoherenceCheckComposition) -> None:
    gate.given_registry_is_unreadable()


@given("wave prose that restates a bare catalog gate-id from the gate stack inline")
def given_prose_restates_a_catalog_gate_id_inline(
    gate: CoherenceCheckComposition,
) -> None:
    gate.given_prose_restates_a_catalog_gate_id_inline()


@given(
    "wave prose that carries valid gates-ref and outputs-ref pointers with zero "
    "inline restatement"
)
def given_prose_with_valid_pointers_zero_restatement(
    gate: CoherenceCheckComposition,
) -> None:
    gate.given_prose_with_valid_pointers_zero_restatement()


# --- When ------------------------------------------------------------------


@when("the maintainer runs the coherence-check gate over that wave")
def when_maintainer_runs_coherence_check(gate: CoherenceCheckComposition) -> None:
    gate.when_maintainer_runs_coherence_check()


# --- Then ------------------------------------------------------------------


@then("the coherence-check gate emits the FAIL verdict")
def then_gate_emits_fail(gate: CoherenceCheckComposition) -> None:
    gate.then_gate_emits_verdict(CoherenceVerdict.FAIL)


@then("the coherence-check gate emits the PASS verdict")
def then_gate_emits_pass(gate: CoherenceCheckComposition) -> None:
    gate.then_gate_emits_verdict(CoherenceVerdict.PASS)


@then("the coherence-check gate emits the INDETERMINATE verdict")
def then_gate_emits_indeterminate(gate: CoherenceCheckComposition) -> None:
    gate.then_gate_emits_verdict(CoherenceVerdict.INDETERMINATE)


@then("the failure diagnostic names the inline restatement it found")
def then_failure_diagnostic_names_inline_restatement(
    gate: CoherenceCheckComposition,
) -> None:
    gate.then_failure_diagnostic_names_inline_restatement()


@then("the indeterminate diagnostic names the unreadable registry")
def then_indeterminate_diagnostic_names_unreadable_registry(
    gate: CoherenceCheckComposition,
) -> None:
    gate.then_indeterminate_diagnostic_names_unreadable_registry()
