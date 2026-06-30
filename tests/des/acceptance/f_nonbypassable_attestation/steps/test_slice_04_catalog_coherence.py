"""pytest-bdd binding for f-nonbypassable-attestation slice-04 (catalog<->wiring coherence).

Driving surface (Mandate-13 pure-function carve-out): the SUT is the pure
coherence reducer ``coherence_offenders`` (the SAME reducer the slice-04 arch test
``tests/build/.../test_arch_catalog_gate_wiring.py`` pins) + the catalog
``_schema.yaml``. For a pure-function slice the "driving port" IS the pure
function. Step bodies delegate to the composition root (``composition_nonbypassable
.py``); no business logic in step bodies (Mandate-12). The composition drives the
SHIPPED reducer over the REAL artifacts (live-catalog scenario) and over distinct
synthetic fixtures (flag / excuse / empty-rationale), never a reimplementation.

S1 (step-text uniqueness within feature scope): every step literal below is
slice-04-UNIQUE -- none collides with the slices 01-03 done-gate verbs in
conftest.py or the per-slice step files (verified: no shared `(step_type,
literal)` key has two bodies). The shared `attestation` fixture lives in conftest.

Active-RED scaffold (atdd_pure -- NOT @skip): the schema-permits-dormant scenario
is RED until DELIVER adds optional ``dormant: {type: string, minLength: 10}`` to
``_schema.yaml`` GateContract (CRITICAL-2) -- at HEAD ``additionalProperties:
false`` rejects the key, so ``then_schema_accepts_dormant`` RED-fails with a
semantic AssertionError (NOT a collection / import / setup error). The other four
scenarios are GREEN behaviour proofs over the shipped reducer. GREEN-completion of
slice-04 = the schema extension lands.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_bdd import given, parsers, scenarios, then, when


if TYPE_CHECKING:
    from .composition_nonbypassable import AttestationComposition


scenarios("../slice-04-catalog-coherence.feature")


# --- Given (slice-04 unique) -----------------------------------------------


@given("the real gate catalog and the live hook firing surfaces")
def given_real_catalog_and_firing_surfaces(attestation: AttestationComposition) -> None:
    attestation.given_real_catalog_and_firing_surfaces()


@given("a catalogue with a wired gate and an orphan gate that no hook fires")
def given_catalogue_with_orphan(attestation: AttestationComposition) -> None:
    attestation.given_catalogue_with_wired_and_orphan_gate()


@given(
    parsers.parse(
        'an unwired catalogued gate declared dormant with the rationale "{rationale}"'
    )
)
def given_unwired_dormant_with_rationale(
    attestation: AttestationComposition, rationale: str
) -> None:
    attestation.given_unwired_dormant_gate(rationale)


@given("an unwired catalogued gate declared dormant with an empty rationale")
def given_unwired_dormant_empty(attestation: AttestationComposition) -> None:
    attestation.given_unwired_dormant_gate("   ")


@given("a catalogued gate contract carrying a dormant rationale")
def given_gate_contract_with_dormant(attestation: AttestationComposition) -> None:
    attestation.given_gate_contract_carrying_dormant()


# --- When (slice-04 unique) ------------------------------------------------


@when("the catalog coherence check runs")
def when_coherence_check_runs(attestation: AttestationComposition) -> None:
    attestation.when_catalog_coherence_check_runs()


@when("the gate contract is validated against the shipped catalog schema")
def when_validated_against_schema(attestation: AttestationComposition) -> None:
    attestation.when_schema_validates_dormant_gate()


# --- Then (slice-04 unique) ------------------------------------------------


@then("no gate is flagged as unwired")
def then_no_gate_flagged(attestation: AttestationComposition) -> None:
    attestation.then_no_gate_is_flagged()


@then("the orphan gate is flagged and named")
def then_orphan_flagged_named(attestation: AttestationComposition) -> None:
    attestation.then_the_offender_is_flagged_and_named("orphan-gate")


@then("the dormant gate is excused")
def then_dormant_excused(attestation: AttestationComposition) -> None:
    attestation.then_the_gate_is_excused("dozing-gate")


@then("the unwired gate is still flagged")
def then_unwired_still_flagged(attestation: AttestationComposition) -> None:
    attestation.then_the_gate_is_still_flagged("dozing-gate")


@then("the catalog schema accepts the dormant rationale")
def then_schema_accepts(attestation: AttestationComposition) -> None:
    attestation.then_schema_accepts_dormant()
