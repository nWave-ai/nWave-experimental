"""Shared step vocabulary for F-LANGUAGE-ADAPTER-PLUGIN-INFRASTRUCTURE.

Mandate-12 (SSOT via Types + Services + DSL): the feature's `.feature` files
share ONE step vocabulary. Each decorator below is a parameterized template
over a typed-enum parameter (from ``domain_types.py``) -- the DSL emerges
from the typed domain concepts, not from one decorator per literal phrase.

Mandate-12 criterion 3: every step body is <=2 statements, ends in a single
``composition.<service>(...)`` call (or a typed-lookup + call), and contains
no control flow. Business logic lives in ``composition.py`` service methods,
never here.

Slice-01 binds the three ATs in `slice-01-walking-skeleton.feature` to the
production composition root via subprocess (Pillar 3 app-as-in-production).
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, then, when

from .composition import LanguageAdapterInfrastructureComposition
from .domain_types import (
    CATALOG_OUTCOME_BY_PHRASE,
    CATALOG_PRESENCE_BY_PHRASE,
    DOCTOR_SHAPE_BY_PHRASE,
    TargetLanguage,
)


@pytest.fixture
def composition() -> LanguageAdapterInfrastructureComposition:
    """The production composition root, fresh per scenario."""
    return LanguageAdapterInfrastructureComposition()


# --- Given: catalog + target-language staging --------------------------------


@given(parsers.parse("the port catalog SSOT is {catalog_presence}"))
def given_catalog_presence(
    composition: LanguageAdapterInfrastructureComposition,
    catalog_presence: str,
) -> None:
    composition.given_catalog_in_state(CATALOG_PRESENCE_BY_PHRASE[catalog_presence])


@given(parsers.parse('the operator targets the "{language}" language'))
def given_target_language(
    composition: LanguageAdapterInfrastructureComposition, language: str
) -> None:
    composition.given_target_language(TargetLanguage(language))


# --- When: production-CLI invocation -----------------------------------------


@when("the port catalog validator runs")
def when_validator_runs(
    composition: LanguageAdapterInfrastructureComposition,
) -> None:
    composition.when_catalog_validator_runs()


@when("the des doctor CLI runs")
def when_doctor_runs(
    composition: LanguageAdapterInfrastructureComposition,
) -> None:
    composition.when_des_doctor_runs()


@when("the language-adapter entry-point discovery runs")
def when_discovery_runs(
    composition: LanguageAdapterInfrastructureComposition,
) -> None:
    composition.when_entry_point_discovery_runs()


# --- Then: universe-bound assertions over port-exposed observables -----------


@then(parsers.parse("the catalog validator reports the catalog as {outcome}"))
def then_validator_outcome(
    composition: LanguageAdapterInfrastructureComposition, outcome: str
) -> None:
    composition.then_catalog_validator_outcome_matches(
        CATALOG_OUTCOME_BY_PHRASE[outcome]
    )


@then("the validator output names the three slice-01 LANGUAGE_BOUND gate CLIs")
def then_validator_lists_floor(
    composition: LanguageAdapterInfrastructureComposition,
) -> None:
    composition.then_catalog_enumerates_minimum_language_bound_ports()


@then(parsers.parse("the doctor report shape is {shape}"))
def then_doctor_shape(
    composition: LanguageAdapterInfrastructureComposition, shape: str
) -> None:
    composition.then_doctor_report_shape_is(DOCTOR_SHAPE_BY_PHRASE[shape])


@then(
    "the doctor report enumerates the language-bound ports missing for the target language"
)
def then_doctor_lists_missing(
    composition: LanguageAdapterInfrastructureComposition,
) -> None:
    composition.then_doctor_report_lists_missing_language_bound_ports()


@then("the entry-point discovery substrate is queryable")
def then_discovery_queryable(
    composition: LanguageAdapterInfrastructureComposition,
) -> None:
    composition.then_entry_point_discovery_succeeds()


@then(
    parsers.parse(
        "the entry-point discovery lists at least {minimum:d} registered plugin"
    )
)
def then_discovery_floor(
    composition: LanguageAdapterInfrastructureComposition, minimum: int
) -> None:
    composition.then_entry_point_discovery_lists_floor(expected_minimum_count=minimum)
