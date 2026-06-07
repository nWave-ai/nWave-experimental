"""Step definitions for slice-04 -- the U4 feature-end intercept + D6 skew.

slice-04 of F-DES-ATDD-PURE-HOOK-GATES (U4 + D6 / Mikado T-H).

Step bodies are delegate-only (Mandate-12 criterion 3): each is a single typed
lookup into the `slice04_domain_types` phrase tables plus one
`FeatureEndInterceptComposition` call (or one `classify_skew` call). All
business logic lives in the production SubagentStop handler and the production
`_classify_hook_version_skew`; the composition root only wires the real I/O.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .slice04_composition import (
    FeatureEndInterceptComposition,
    FeatureEndOutcomeResult,
    classify_skew,
)
from .slice04_domain_types import (
    FEATURE_END_OUTCOME_BY_PHRASE,
    LEDGER_SHAPE_BY_PHRASE,
    LedgerShape,
)


scenarios("../feature-end-version-skew.feature")


@pytest.fixture
def composition(tmp_path: Path) -> FeatureEndInterceptComposition:
    comp = FeatureEndInterceptComposition(tmp_path)
    comp.init_repo()
    return comp


@pytest.fixture
def outcome_holder() -> dict[str, object]:
    return {}


# --- U4 feature-end intercept scenarios -------------------------------------


@given("an atdd_pure feature whose every planned slice is verified in the ledger")
def _given_all_verified(composition: FeatureEndInterceptComposition) -> None:
    composition.seed_all_slices_verified()


@given(parsers.parse("an atdd_pure feature whose ledger is {ledger_phrase}"))
def _given_ledger_shape(
    composition: FeatureEndInterceptComposition, ledger_phrase: str
) -> None:
    shape = LEDGER_SHAPE_BY_PHRASE[ledger_phrase]
    if shape is LedgerShape.CORRUPT:
        composition.corrupt_the_ledger()
    elif shape is LedgerShape.FAULT_INJECTED:
        composition.inject_handler_fault()


@given("the feature-end cycle recorded its refactor and review verdict")
def _given_cycle_complete(composition: FeatureEndInterceptComposition) -> None:
    composition.seed_feature_end_cycle_complete()


@given(parsers.parse("the feature-end cycle is missing its {missing_record} record"))
def _given_cycle_incomplete(
    composition: FeatureEndInterceptComposition, missing_record: str
) -> None:
    composition.seed_feature_end_cycle_missing(missing_record)


@given("the feature-end review agent returns from the F_FINAL_REVIEW phase")
def _given_feature_end_return(composition: FeatureEndInterceptComposition) -> None:
    composition.write_f_final_review_transcript()


@when("the SubagentStop hook processes the return")
def _when_hook_runs(
    composition: FeatureEndInterceptComposition,
    outcome_holder: dict[str, object],
) -> None:
    outcome_holder["result"] = composition.run_subagent_stop_hook()


@then(parsers.parse("the feature-end intercept {outcome_phrase}"))
def _then_outcome(outcome_holder: dict[str, object], outcome_phrase: str) -> None:
    result = outcome_holder["result"]
    assert isinstance(result, FeatureEndOutcomeResult)
    assert result.outcome == FEATURE_END_OUTCOME_BY_PHRASE[outcome_phrase]


@then(parsers.parse("the intercept reports event {decision_event}"))
def _then_decision_event(
    outcome_holder: dict[str, object], decision_event: str
) -> None:
    result = outcome_holder["result"]
    assert isinstance(result, FeatureEndOutcomeResult)
    assert result.decision_event == decision_event


@then("the hook exits with code zero")
def _then_exit_zero(outcome_holder: dict[str, object]) -> None:
    result = outcome_holder["result"]
    assert isinstance(result, FeatureEndOutcomeResult)
    assert result.exit_code == 0


# --- D6 hook-version skew classifier scenarios ------------------------------


@given(
    parsers.parse(
        "an installed hook stamp {installed} and a running checkout {checkout}"
    )
)
def _given_skew_inputs(
    outcome_holder: dict[str, object], installed: str, checkout: str
) -> None:
    # The literal "absent" Gherkin token maps to a missing stamp (None).
    outcome_holder["installed"] = None if installed == "absent" else installed
    outcome_holder["checkout"] = checkout


@when("the session-start skew detector classifies the hook version")
def _when_classify(outcome_holder: dict[str, object]) -> None:
    installed = outcome_holder["installed"]
    checkout = outcome_holder["checkout"]
    assert installed is None or isinstance(installed, str)
    assert isinstance(checkout, str)
    outcome_holder["skew_case"] = classify_skew(installed, checkout)


@then(parsers.parse("the skew case is {skew_case}"))
def _then_skew_case(outcome_holder: dict[str, object], skew_case: str) -> None:
    assert outcome_holder["skew_case"] == skew_case
