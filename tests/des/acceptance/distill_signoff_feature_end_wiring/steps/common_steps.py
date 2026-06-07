"""Shared step vocabulary for the fix-distill-signoff-feature-end-wiring suite.

Mandate-12 (SSOT via Types + Services + DSL): the slice's `.feature` file
shares ONE step vocabulary. Each decorator below is a parameterized template
over a typed-enum parameter (from ``domain_types.py``) -- the DSL emerges
from the typed domain concepts, not from one decorator per literal phrase.

Mandate-12 criterion 3: every step body is <=2 statements, ends in a single
``composition.<service>(...)`` call (or a typed-lookup + call), and contains
no control flow. Business logic lives in ``composition.py`` service methods,
never here.

The slice ``test_slice_01_*.py`` file imports ``*`` from this module and
calls ``scenarios(...)`` on its own ``.feature`` file -- pytest-bdd resolves
the steps from this shared module (Mandate 10 shared-vocabulary contract).
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, then, when

from .composition import DistillSignoffFeatureEndWiringComposition
from .domain_types import (
    LEDGER_STATE_BY_PHRASE,
    MISSING_OUTCOME_BY_PHRASE,
    TOUCHPOINT_BY_PHRASE,
)


@pytest.fixture
def composition() -> DistillSignoffFeatureEndWiringComposition:
    """The production composition root, fresh per scenario."""
    return DistillSignoffFeatureEndWiringComposition()


# --- Given: feature-end ledger staging ---------------------------------------


@given(
    parsers.parse(
        "a feature whose feature-end ledger is staged in the {ledger_state} condition"
    )
)
def given_ledger_state(
    composition: DistillSignoffFeatureEndWiringComposition, ledger_state: str
) -> None:
    composition.given_feature_end_ledger_state(LEDGER_STATE_BY_PHRASE[ledger_state])


# --- When: production-code invocation ----------------------------------------


@when("the feature-end completion enforcer checks the required feature-end records")
def when_u4_enforcer_runs(
    composition: DistillSignoffFeatureEndWiringComposition,
) -> None:
    composition.when_u4_enforcer_runs()


@when("the verify_deliver_integrity CLI runs on the feature")
def when_cli_runs(composition: DistillSignoffFeatureEndWiringComposition) -> None:
    composition.when_verify_deliver_integrity_cli_runs()


# --- Then: universe-bound assertions over port-exposed observables -----------


@then(
    parsers.parse(
        "the {touchpoint} heartbeat is {missing_outcome} in the missing-record set"
    )
)
def then_missing_outcome(
    composition: DistillSignoffFeatureEndWiringComposition,
    touchpoint: str,
    missing_outcome: str,
) -> None:
    composition.then_missing_record_set_matches(
        TOUCHPOINT_BY_PHRASE[touchpoint],
        MISSING_OUTCOME_BY_PHRASE[missing_outcome],
    )


@then(
    "the feature is not permitted to be declared done when the missing-record"
    " set is non-empty"
)
def then_feature_blocked_when_missing(
    composition: DistillSignoffFeatureEndWiringComposition,
) -> None:
    composition.then_feature_is_not_permitted_when_missing_records()


@then("the missing-record set is empty")
def then_missing_set_empty(
    composition: DistillSignoffFeatureEndWiringComposition,
) -> None:
    composition.then_missing_record_set_is_empty()


@then("the feature is permitted to be declared done")
def then_feature_permitted(
    composition: DistillSignoffFeatureEndWiringComposition,
) -> None:
    composition.then_feature_is_permitted()


@then("the CLI exits with a feature-end-cycle-incomplete verdict")
def then_cli_reports_incomplete(
    composition: DistillSignoffFeatureEndWiringComposition,
) -> None:
    composition.then_cli_reports_feature_end_cycle_incomplete()


@then(
    parsers.parse(
        "the verdict names the {touchpoint} heartbeat as a missing required record"
    )
)
def then_cli_names_touchpoint(
    composition: DistillSignoffFeatureEndWiringComposition, touchpoint: str
) -> None:
    composition.then_cli_names_touchpoint_heartbeat_missing(
        TOUCHPOINT_BY_PHRASE[touchpoint]
    )
