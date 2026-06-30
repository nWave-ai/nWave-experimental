"""pytest-bdd binding for f-wave-contract-coherence slice-07 (epic-delta reconciliation).

Driving surface (Mandate-13 driving-port-only): the SHIPPED flow-v2 epic-delta
parsed through the production feature-plan parser, the REAL
``des validate-feature-delta --require-feature-plan`` subprocess, and the SHIPPED
closure-scorecard FEATURES list (the GOAL CONTRACT, read never run). Step bodies
delegate to the composition root (composition_epic_delta_reconciliation.py); no
business logic in step bodies (Mandate-12).

Active-RED scaffold (atdd_pure -- NOT @skip): each scenario is RED until DELIVER ADDs
the 8 missing Feature Plan rows to the SHIPPED epic-delta so its inventory matches the
scorecard. Every case fails with a semantic AssertionError naming the EXACT missing
feature-ids, never a collection / import / setup error.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_epic_delta_reconciliation import (
    EpicDeltaReconciliationComposition,
)


scenarios("../epic-delta-reconciliation.feature")


@pytest.fixture
def reconciliation() -> EpicDeltaReconciliationComposition:
    return EpicDeltaReconciliationComposition()


# --- Given -----------------------------------------------------------------


@given("the shipped flow-v2 epic-delta and the closure scorecard")
def given_shipped_epic_delta_and_scorecard(
    reconciliation: EpicDeltaReconciliationComposition,
) -> None:
    reconciliation.given_shipped_epic_delta_and_scorecard()


# --- When ------------------------------------------------------------------


@when("the epic-delta Feature Plan is read")
def when_epic_delta_feature_plan_is_read(
    reconciliation: EpicDeltaReconciliationComposition,
) -> None:
    reconciliation.when_epic_delta_feature_plan_is_read()


@when("the feature-plan validator runs over the epic-delta")
def when_validator_runs_over_epic_delta(
    reconciliation: EpicDeltaReconciliationComposition,
) -> None:
    reconciliation.when_validator_runs_over_epic_delta()


@when("the epic-delta Feature Plan id set and the scorecard feature-id set are read")
def when_both_id_sets_are_read(
    reconciliation: EpicDeltaReconciliationComposition,
) -> None:
    reconciliation.when_both_id_sets_are_read()


# --- Then ------------------------------------------------------------------


@then("the epic-delta Feature Plan lists every feature the live set declares")
def then_epic_delta_lists_every_live_feature(
    reconciliation: EpicDeltaReconciliationComposition,
) -> None:
    reconciliation.then_epic_delta_lists_every_live_feature()


@then("the validator accepts an epic-delta Feature Plan covering every live feature")
def then_validator_accepts_complete_feature_plan(
    reconciliation: EpicDeltaReconciliationComposition,
) -> None:
    reconciliation.then_validator_accepts_complete_feature_plan()


@then("the epic-delta feature-id set equals the scorecard feature-id set")
def then_epic_delta_id_set_equals_scorecard_id_set(
    reconciliation: EpicDeltaReconciliationComposition,
) -> None:
    reconciliation.then_epic_delta_id_set_equals_scorecard_id_set()
