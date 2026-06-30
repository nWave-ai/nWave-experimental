"""pytest-bdd binding for the f-coherence-and-attestation slice-03 scenarios (gate-G).

Driving surface (Mandate-13 driving-port-only, Layer 3 composition): the REAL
gate-G mechanism (the mechanical design↔AT coherence diff) via the production
composition root. Step bodies delegate to the composition root
(composition_slice_03_gate_g.py); no business logic in step bodies (Mandate-12).
The ``<divergence>`` parameter is parsed once into the typed ``CoherenceCase``
enum, so ONE scenario shape ranges over the confirmable-divergence kinds.

active-RED scaffold (atdd_pure -- NOT @skip): every scenario is RED until DELIVER
lands the slice-03 gate-G seam (``src/des/cli/gate_g.py`` -- the mechanical diff
over the slice-01/02 CodeFactPort substrate). Each scenario fails with a semantic
AssertionError naming the missing gate-G mechanism, never a collection / import /
setup error.

STEP-TEXT UNIQUENESS (S1): every literal/template step phrase below is DISTINCT
from the slice-01 + slice-02 step phrases. slice-01 uses "is asked for the fact
through the CodeFactPort"; slice-02 uses "answers the structural fact" /
"negotiates the best available provider"; slice-03 uses "diffs the design contract
against the acceptance tests" / "a design contract whose ..." -- no pytest-bdd
global-registry shadow.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_03_gate_g import GateGComposition
from .domain_types_slice_03_gate_g import CoherenceCase, ContractInput, GateVerdict


scenarios("../slice-03-gate-g-design-at-coherence.feature")


# Divergence wire-token (kebab-lowercase) -> typed CoherenceCase.
_CASE_BY_DIVERGENCE = {
    "dropped-row": CoherenceCase.DROPPED_ROW,
    "signature-mismatch": CoherenceCase.SIGNATURE_MISMATCH,
}


@pytest.fixture
def gate_g() -> GateGComposition:
    return GateGComposition()


# --- Given -----------------------------------------------------------------


@given(
    "a design contract whose example-table rows and the acceptance scenarios are "
    "bijective"
)
def given_bijective_contract(gate_g: GateGComposition) -> None:
    gate_g.given_coherence_case(CoherenceCase.BIJECTIVE)


@given(
    parsers.parse(
        "a design contract with a confirmable {divergence} against the acceptance tests"
    )
)
def given_confirmable_divergence(gate_g: GateGComposition, divergence: str) -> None:
    gate_g.given_coherence_case(_CASE_BY_DIVERGENCE[divergence])


@given(
    "a design contract whose prose suspects a drift the row-level diff cannot confirm"
)
def given_suspected_unconfirmable_drift(gate_g: GateGComposition) -> None:
    gate_g.given_coherence_case(CoherenceCase.SUSPECTED_UNCONFIRMABLE)


@given(
    "a design contract whose acceptance tests are in a language the inspection "
    "adapter cannot parse"
)
def given_unsupported_language(gate_g: GateGComposition) -> None:
    gate_g.given_contract_input(ContractInput.ADAPTER_ABSENT)


# --- When ------------------------------------------------------------------


@when("the coherence gate diffs the design contract against the acceptance tests")
def when_gate_g_diffs(gate_g: GateGComposition, tmp_path: Path) -> None:
    if gate_g._contract_input is ContractInput.ADAPTER_ABSENT:
        gate_g.when_gate_g_runs_with_unsupported_adapter(tmp_path)
    else:
        gate_g.when_gate_g_diffs_design_against_ats(tmp_path)


# --- Then ------------------------------------------------------------------


@then("the coherence gate returns a passing verdict")
def then_passing_verdict(gate_g: GateGComposition) -> None:
    gate_g.then_verdict_is(GateVerdict.PASS)


@then("the coherence gate returns a failing verdict")
def then_failing_verdict(gate_g: GateGComposition) -> None:
    gate_g.then_verdict_is(GateVerdict.FAIL)


@then("the coherence gate names the divergence in a diagnostic")
def then_diagnostic_names_divergence(gate_g: GateGComposition) -> None:
    gate_g.then_diagnostic_names_the_divergence()


@then("the coherence gate returns an unverified verdict")
def then_unverified_verdict(gate_g: GateGComposition) -> None:
    gate_g.then_verdict_is(GateVerdict.UNVERIFIED)


@then("the coherence gate surfaces the North-Star cap loudly")
def then_north_star_cap_loud(gate_g: GateGComposition) -> None:
    gate_g.then_north_star_cap_is_surfaced_loud()


@then("the coherence gate returns an indeterminate verdict")
def then_indeterminate_verdict(gate_g: GateGComposition) -> None:
    gate_g.then_verdict_is(GateVerdict.INDETERMINATE)


@then("the coherence gate did not run a real mechanical diff")
def then_gate_g_did_not_run(gate_g: GateGComposition) -> None:
    gate_g.then_gate_g_did_not_run()
