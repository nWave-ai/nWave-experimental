"""pytest-bdd binding for the f-coherence-and-attestation slice-04 scenarios.

Driving surface (Mandate-13 driving-port-only, Layer 3 composition): the REAL
self-attest classifier (the dual-source verdict layer) via the production
composition root. Step bodies delegate to the composition root
(composition_slice_04_self_attest.py); no business logic in step bodies
(Mandate-12). The ``<attestation>`` parameter is parsed once into the typed
``AttestationCase`` enum and the ``<verdict>`` into the typed ``GateVerdict``,
so ONE Scenario-Outline shape ranges over the NO-floor / degrade cases.

active-RED scaffold (atdd_pure -- NOT @skip): every scenario is RED until DELIVER
lands the slice-04 self-attest seam (``src/des/domain/self_attest.py`` -- the
classifier EXTENDING the keyless content-seal). Each scenario fails with a
semantic AssertionError naming the missing classifier, never a collection /
import / setup error.

STEP-TEXT UNIQUENESS (S1): every literal/template step phrase below is DISTINCT
from the slice-01 + slice-02 + slice-03 step phrases. slice-01 uses "is asked for
the fact through the CodeFactPort"; slice-02 uses "answers the structural fact" /
"negotiates the best available provider"; slice-03 uses "diffs the design contract
against the acceptance tests" / "a design contract whose ..."; slice-04 uses
"the self-attest layer classifies the gate verdict" / "a gate verdict that is ..."
/ "a gate verdict carrying mechanical evidence ..." -- no pytest-bdd
global-registry shadow.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_04_self_attest import SelfAttestComposition
from .domain_types_slice_04_self_attest import AttestationCase, GateVerdict


scenarios("../slice-04-self-attest-verdict-layer.feature")


# Attestation Gherkin phrase -> typed AttestationCase (NO-floor / degrade cases).
_CASE_BY_ATTESTATION = {
    "a bare reviewer say-so with no mechanical evidence": (
        AttestationCase.BARE_LLM_NO_EVIDENCE
    ),
    "a disagreement between the mechanical and reviewer sources": (
        AttestationCase.DUAL_SOURCE_DIVERGENCE
    ),
    "a mechanical leg that timed out before it completed": (
        AttestationCase.WATCHDOG_TIMEOUT
    ),
}

# Verdict wire-token (kebab/lowercase) -> typed GateVerdict.
_VERDICT_BY_TOKEN = {
    "passing": GateVerdict.PASS,
    "unverified": GateVerdict.UNVERIFIED,
    "indeterminate": GateVerdict.INDETERMINATE,
}


@pytest.fixture
def self_attest() -> SelfAttestComposition:
    return SelfAttestComposition()


# --- Given -----------------------------------------------------------------


@given(
    "a gate verdict carrying mechanical evidence where the mechanical and reviewer "
    "sources agree"
)
def given_mechanically_grounded_agreement(self_attest: SelfAttestComposition) -> None:
    self_attest.given_attestation_case(AttestationCase.MECHANICAL_EVIDENCE_AGREE)


@given(parsers.parse("a gate verdict that is {attestation}"))
def given_no_floor_attestation(
    self_attest: SelfAttestComposition, attestation: str
) -> None:
    self_attest.given_attestation_case(_CASE_BY_ATTESTATION[attestation])


# --- When ------------------------------------------------------------------


@when("the self-attest layer classifies the gate verdict")
def when_self_attest_classifies(self_attest: SelfAttestComposition) -> None:
    self_attest.when_self_attest_classifies_the_verdict()


# --- Then ------------------------------------------------------------------


@then("the self-attest layer returns a passing verdict")
def then_passing_verdict(self_attest: SelfAttestComposition) -> None:
    self_attest.then_verdict_is(GateVerdict.PASS)


@then(parsers.parse("the self-attest layer returns a {verdict} verdict"))
def then_no_floor_verdict(self_attest: SelfAttestComposition, verdict: str) -> None:
    self_attest.then_verdict_is(_VERDICT_BY_TOKEN[verdict])


@then(
    parsers.parse(
        "the self-attest layer names the floor as {cause_fragment} in the reason"
    )
)
def then_reason_names_floor(
    self_attest: SelfAttestComposition, cause_fragment: str
) -> None:
    self_attest.then_reason_names_the_floor(cause_fragment)
