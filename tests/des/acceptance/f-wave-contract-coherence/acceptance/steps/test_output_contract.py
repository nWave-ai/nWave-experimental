"""pytest-bdd binding for f-wave-contract-coherence slice-04 (output-contract SSOT MOVE).

Driving surface (Mandate-13 driving-port-only, real artifacts): the SHIPPED registry
nWave/waves/discuss.yaml + the SHIPPED central schema
schemas/feature-delta-tier1-sections.yaml + the SHIPPED wave-contract JSON-Schema
nWave/waves/_schema.yaml, all read from the repo (Layer 3 composition). Step bodies
delegate to the composition root (composition_output_contract.py); no business logic
in step bodies (Mandate-12).

Active-RED scaffold (atdd_pure -- NOT @skip): each scenario is RED until DELIVER
removes the waves.DISCUSS.required_sections block from the central schema (the MOVE),
leaving the registry output_contract as the sole authoring locus. Every case fails
with a semantic AssertionError naming the surviving duplicate copy, never a
collection / import / setup error.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_output_contract import OutputContractMoveComposition


scenarios("../output-contract-ssot.feature")


@pytest.fixture
def move() -> OutputContractMoveComposition:
    return OutputContractMoveComposition()


# --- Given -----------------------------------------------------------------


@given(
    "the shipped wave-contract registry and the central feature-delta schema are read from the repo"
)
def given_shipped_registry_and_central_schema_are_read(
    move: OutputContractMoveComposition,
) -> None:
    move.given_shipped_registry_and_central_schema_are_read()


# --- When ------------------------------------------------------------------


@when(
    "the maintainer resolves the DISCUSS section list from the canonical authoring locus"
)
def when_maintainer_resolves_discuss_section_list_from_canonical_locus(
    move: OutputContractMoveComposition,
) -> None:
    move.when_maintainer_resolves_discuss_section_list_from_canonical_locus()


@when(
    'a greenfield feature is checked for the mandatory "Wave-Decision Reconciliation" DISCUSS section'
)
def when_greenfield_feature_checked_for_mandatory_section(
    move: OutputContractMoveComposition,
) -> None:
    move.when_greenfield_feature_checked_for_mandatory_section()


# --- Then ------------------------------------------------------------------


@then(
    "the registry output contract is schema-valid and authors the full DISCUSS section list"
)
def then_registry_output_contract_is_schema_valid_and_complete(
    move: OutputContractMoveComposition,
) -> None:
    move.then_registry_output_contract_is_schema_valid_and_complete()


@then("the registry is the only locus that authors the DISCUSS section list")
def then_registry_is_the_only_authoring_locus(
    move: OutputContractMoveComposition,
) -> None:
    move.then_registry_is_the_only_authoring_locus()


@then(
    "the section satisfies the presence-check through its greenfield degradation literal"
)
def then_section_satisfies_greenfield_presence_via_degradation_literal(
    move: OutputContractMoveComposition,
) -> None:
    move.then_section_satisfies_greenfield_presence_via_degradation_literal()


@then("the greenfield degradation literal is authored only in the registry")
def then_greenfield_literal_is_authored_only_in_registry(
    move: OutputContractMoveComposition,
) -> None:
    move.then_greenfield_literal_is_authored_only_in_registry()


@then(
    "the central feature-delta schema no longer carries the DISCUSS required-sections block"
)
def then_central_schema_no_longer_carries_discuss_required_sections(
    move: OutputContractMoveComposition,
) -> None:
    move.then_central_schema_no_longer_carries_discuss_required_sections()


@then(
    "the DISCUSS section list resolves from the registry as the only surviving source"
)
def then_section_list_resolves_from_registry_as_only_surviving_source(
    move: OutputContractMoveComposition,
) -> None:
    move.then_section_list_resolves_from_registry_as_only_surviving_source()
