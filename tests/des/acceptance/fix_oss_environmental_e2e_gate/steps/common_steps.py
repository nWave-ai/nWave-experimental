"""Shared step vocabulary for the fix-oss-environmental-e2e-gate suite.

Mandate-12 (SSOT via Types + Services + DSL): the four slice `.feature` files
share ONE step vocabulary. Each decorator below is a parameterized template
over a typed-enum parameter (from `domain_types.py`) -- the DSL emerges from
the typed domain concepts, not from one decorator per literal phrase.

Mandate-12 criterion 3: every step body is <=2 statements, ends in a single
`composition.<service>(...)` call (or a typed-lookup + call), and contains no
control flow. Business logic lives in `composition.py` service methods, never
here.

The slice `test_slice_NN_*.py` files import `*` from this module and call
`scenarios(...)` on their own `.feature` file -- pytest-bdd resolves the steps
from this shared module (Mandate 10 shared-vocabulary contract).
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, then, when

from .composition import EnvironmentalE2eGateComposition
from .domain_types import (
    DONE_GATE_VERDICT_BY_PHRASE,
    EXIT_BY_MEANING,
    FAIL_CONDITION_BY_PHRASE,
    GIT_STATE_BY_PHRASE,
    HOOK_OFFERED_BY_OUTCOME,
    INTERACTIVITY_BY_PHRASE,
    LEDGER_RECORDS_BY_PHRASE,
    SITUATION_BY_PHRASE,
    VERDICT_BY_PHRASE,
    FeatureEndRecord,
)


@pytest.fixture
def composition() -> EnvironmentalE2eGateComposition:
    """The production composition root, fresh per scenario."""
    return EnvironmentalE2eGateComposition()


# --- Given: feature staging --------------------------------------------------


@given(
    parsers.parse(
        "a feature that ships a packaged CLI module with an environmental e2e test"
    )
)
def given_feature_passing_e2e(composition: EnvironmentalE2eGateComposition) -> None:
    composition.given_feature_with_environmental_e2e(
        SITUATION_BY_PHRASE["green against the installed artifact"]
    )


@given(
    parsers.parse(
        "a feature that ships a packaged CLI module with a failing environmental e2e test"
    )
)
def given_feature_failing_e2e(composition: EnvironmentalE2eGateComposition) -> None:
    composition.given_feature_with_environmental_e2e(
        SITUATION_BY_PHRASE["red against the installed artifact"]
    )


@given(
    parsers.parse('a feature whose environmental e2e is in the "{situation}" condition')
)
def given_feature_in_situation(
    composition: EnvironmentalE2eGateComposition, situation: str
) -> None:
    composition.given_feature_with_environmental_e2e(SITUATION_BY_PHRASE[situation])


@given(parsers.parse('a feature whose environmental e2e gate run "{fail_condition}"'))
def given_gate_run_fail_condition(
    composition: EnvironmentalE2eGateComposition, fail_condition: str
) -> None:
    composition.given_gate_run_fail_condition(FAIL_CONDITION_BY_PHRASE[fail_condition])


@given("a feature whose delta carries no environmental e2e declaration block")
def given_feature_no_e2e_block(
    composition: EnvironmentalE2eGateComposition,
) -> None:
    composition.given_feature_without_environmental_e2e_block()


@given(parsers.parse("a feature whose feature-end ledger holds {records}"))
def given_feature_end_ledger_holds(
    composition: EnvironmentalE2eGateComposition, records: str
) -> None:
    composition.given_feature_end_ledger_records(LEDGER_RECORDS_BY_PHRASE[records])


@given(
    "a feature whose feature-end cycle ran the environmental e2e gate to a passing verdict"
)
def given_feature_end_passing(
    composition: EnvironmentalE2eGateComposition,
) -> None:
    composition.given_feature_end_ledger_records(frozenset(FeatureEndRecord))


@given("a feature whose feature-end cycle never ran the environmental e2e gate")
def given_feature_end_never_ran(
    composition: EnvironmentalE2eGateComposition,
) -> None:
    composition.given_feature_end_ledger_records(frozenset())


@given(
    parsers.parse(
        'an install environment that "{git_state}" git and runs "{interactivity}"'
    )
)
def given_install_environment(
    composition: EnvironmentalE2eGateComposition, git_state: str, interactivity: str
) -> None:
    composition.given_install_environment(
        GIT_STATE_BY_PHRASE[git_state], INTERACTIVITY_BY_PHRASE[interactivity]
    )


@given("an install environment that lacks git entirely")
def given_install_environment_no_git(
    composition: EnvironmentalE2eGateComposition,
) -> None:
    composition.given_install_environment(
        GIT_STATE_BY_PHRASE["lacks"], INTERACTIVITY_BY_PHRASE["interactively"]
    )


@given(
    "the environmental e2e gate is registered as a shipped command and named in the "
    "feature-end orchestration step"
)
def given_gate_wired(composition: EnvironmentalE2eGateComposition) -> None:
    composition.given_gate_wired_into_floor()


# --- When: gate invocation ---------------------------------------------------


@when(
    "the developer runs the environmental e2e gate in run mode against the delivered artifact"
)
@when("the developer runs the environmental e2e gate in run mode")
def when_run_gate_run_mode(composition: EnvironmentalE2eGateComposition) -> None:
    composition.result = composition.run_gate_in_run_mode()


@when("the developer runs the environmental e2e gate in verify-authored mode")
def when_run_gate_verify_authored(
    composition: EnvironmentalE2eGateComposition,
) -> None:
    composition.result = composition.run_gate_in_verify_authored_mode()


@when("the feature-end done-gate evaluates whether the feature may be declared done")
def when_evaluate_done_gate(composition: EnvironmentalE2eGateComposition) -> None:
    composition.done_gate_outcome = composition.evaluate_done_gate()


@when("the feature-end completion enforcer checks the required feature-end records")
def when_check_required_records(
    composition: EnvironmentalE2eGateComposition,
) -> None:
    composition.missing_records = composition.check_required_feature_end_records()


@when("nWave offers its optional defense-in-depth layers")
def when_offer_optional_layers(
    composition: EnvironmentalE2eGateComposition,
) -> None:
    composition.offer_optional_layers()


@when(
    "the gate command is dropped from the shipped command set or its token is removed "
    "from the feature-end orchestration step"
)
def when_unwire_gate(composition: EnvironmentalE2eGateComposition) -> None:
    composition.unwire_gate_from_floor()
    composition.result = composition.arch_test_wiring_result()


# --- Then: outcome assertions ------------------------------------------------


@then("the gate reports the environmental e2e verdict as passing")
def then_verdict_passing(composition: EnvironmentalE2eGateComposition) -> None:
    assert composition.result.verdict == VERDICT_BY_PHRASE["pass"]


@then("the gate reports the environmental e2e verdict as failing")
def then_verdict_failing(composition: EnvironmentalE2eGateComposition) -> None:
    assert composition.result.verdict == VERDICT_BY_PHRASE["fail"]


@then(parsers.parse('the gate verdict token reads "{verdict}"'))
def then_verdict_token(
    composition: EnvironmentalE2eGateComposition, verdict: str
) -> None:
    assert composition.result.verdict == VERDICT_BY_PHRASE[verdict]


@then("the gate exit status indicates success")
def then_exit_success(composition: EnvironmentalE2eGateComposition) -> None:
    assert composition.result.exit_code == EXIT_BY_MEANING["success"]


@then("the gate exit status indicates a check failed")
def then_exit_check_failed(composition: EnvironmentalE2eGateComposition) -> None:
    assert composition.result.exit_code == EXIT_BY_MEANING["check failed"]


@then("the gate exit status indicates a parse or environment failure")
def then_exit_parse_io(composition: EnvironmentalE2eGateComposition) -> None:
    assert (
        composition.result.exit_code
        == EXIT_BY_MEANING["a parse or environment failure"]
    )


@then("the gate exit status indicates a mis-scoped feature")
def then_exit_misscoped(composition: EnvironmentalE2eGateComposition) -> None:
    assert composition.result.exit_code == EXIT_BY_MEANING["a mis-scoped feature"]


@then(parsers.parse('the gate exit status is "{exit_meaning}"'))
def then_exit_status_is(
    composition: EnvironmentalE2eGateComposition, exit_meaning: str
) -> None:
    assert composition.result.exit_code == EXIT_BY_MEANING[exit_meaning]


@then(
    "the gate writes a results record stamped with a freshness digest over the wheel, "
    "the e2e files, and the continuous-integration job closure"
)
def then_results_record_has_digest(
    composition: EnvironmentalE2eGateComposition,
) -> None:
    assert composition.result.has_freshness_digest is True


@then("the gate reports the feature as mis-scoped")
def then_feature_misscoped(composition: EnvironmentalE2eGateComposition) -> None:
    assert composition.result.verdict == VERDICT_BY_PHRASE["misscoped"]


@then("the feature-end ledger holds no trusted positive verification record")
def then_no_trusted_verification_record(
    composition: EnvironmentalE2eGateComposition,
) -> None:
    assert composition.feature_end_has_trusted_verification_record() is False


@then("the developer's repository working tree is unchanged")
@then("no file under the developer's source tree was written during the gate run")
def then_repo_unchanged(composition: EnvironmentalE2eGateComposition) -> None:
    assert composition.repository_working_tree_is_unchanged() is True


@then("the gate writes an environmental e2e deferral marker for the feature")
def then_deferral_marker_written(
    composition: EnvironmentalE2eGateComposition,
) -> None:
    assert composition.result.deferral_marker_written is True


@then(
    "the gate diagnostic names the absent environmental e2e declaration as the re-scope trigger"
)
@then("the failure diagnostic names which wiring point lost the gate")
def then_diagnostic_non_empty(
    composition: EnvironmentalE2eGateComposition,
) -> None:
    assert composition.result.diagnostic != ""


@then(parsers.parse("the done-gate verdict is {verdict}"))
def then_done_gate_verdict_is(
    composition: EnvironmentalE2eGateComposition, verdict: str
) -> None:
    assert composition.done_gate_outcome == DONE_GATE_VERDICT_BY_PHRASE[verdict]


@then("the feature is permitted to be declared done")
def then_feature_may_be_done(
    composition: EnvironmentalE2eGateComposition,
) -> None:
    assert composition.done_gate_outcome == DONE_GATE_VERDICT_BY_PHRASE["permitted"]


@then("the feature is not permitted to be declared done")
@then("the feature-end done-gate still blocks the feature from being declared done")
def then_done_gate_blocks(composition: EnvironmentalE2eGateComposition) -> None:
    assert composition.done_gate_outcome != DONE_GATE_VERDICT_BY_PHRASE["permitted"]


@then(
    "evaluating the feature-end done-gate blocks the feature from being declared done"
)
def then_evaluating_done_gate_blocks(
    composition: EnvironmentalE2eGateComposition,
) -> None:
    assert composition.evaluate_done_gate() != DONE_GATE_VERDICT_BY_PHRASE["permitted"]


@then(
    "the feature-end ledger carries the environmental e2e heartbeat recorded before the verdict"
)
def then_ledger_heartbeat_before_verdict(
    composition: EnvironmentalE2eGateComposition,
) -> None:
    assert composition.heartbeat_precedes_verified_in_ledger() is True


@then(
    "the enforcer reports the environmental e2e heartbeat as a missing required record"
)
def then_heartbeat_is_missing_record(
    composition: EnvironmentalE2eGateComposition,
) -> None:
    assert FeatureEndRecord.HEARTBEAT in composition.missing_records


@then(parsers.parse('the git pre-push hook is "{hook_outcome}"'))
def then_hook_outcome(
    composition: EnvironmentalE2eGateComposition, hook_outcome: str
) -> None:
    assert (
        composition.git_prepush_hook_was_offered()
        == HOOK_OFFERED_BY_OUTCOME[hook_outcome]
    )


@then("no git pre-push hook is offered")
def then_no_hook_offered(composition: EnvironmentalE2eGateComposition) -> None:
    assert composition.git_prepush_hook_was_offered() is False


@then("the environmental e2e gate floor is installed regardless")
def then_floor_installed(composition: EnvironmentalE2eGateComposition) -> None:
    assert composition.gate_floor_was_installed() is True


@then("the gate-wiring architecture test fails")
def then_arch_test_fails(composition: EnvironmentalE2eGateComposition) -> None:
    assert composition.result.exit_code == EXIT_BY_MEANING["check failed"]
