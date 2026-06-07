"""Step definitions for slice-02 -- the U2 G_COMMIT SubagentStop exit gate.

slice-02 of F-DES-ATDD-PURE-HOOK-GATES (U2 / Mikado T-G).

Step bodies are delegate-only (Mandate-12 criterion 3): each is a single typed
lookup into the `slice02_domain_types` phrase tables plus one
`G_CommitInterceptComposition` call. All business logic lives in the production
SubagentStop handler; the composition root only wires the real hook subprocess.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .slice02_composition import G_CommitInterceptComposition, InterceptOutcome
from .slice02_domain_types import (
    COMMIT_SHAPE_BY_PHRASE,
    GATE_OUTCOME_BY_PHRASE,
    CommitShape,
)


scenarios("../g-commit-exit-gate.feature")


@pytest.fixture
def composition(tmp_path: Path) -> G_CommitInterceptComposition:
    comp = G_CommitInterceptComposition(tmp_path)
    comp.init_repo()
    return comp


@pytest.fixture
def outcome_holder() -> dict[str, InterceptOutcome]:
    return {}


@given("an atdd_pure crafter has committed a complete slice commit")
def _given_complete_commit(composition: G_CommitInterceptComposition) -> None:
    composition.make_head_commit(CommitShape.COMPLETE)


@given(parsers.parse("an atdd_pure crafter has committed {commit_phrase}"))
def _given_commit_shape(
    composition: G_CommitInterceptComposition, commit_phrase: str
) -> None:
    composition.make_head_commit(COMMIT_SHAPE_BY_PHRASE[commit_phrase])


@given("the crafter returns from the G_COMMIT phase")
def _given_g_commit_return(composition: G_CommitInterceptComposition) -> None:
    composition.write_g_commit_transcript()


@given("the crafter transcript carries a stale earlier dispatch block")
def _given_two_block_transcript(
    composition: G_CommitInterceptComposition,
) -> None:
    composition.write_two_block_transcript()


@given("a fault is injected inside the G_COMMIT intercept")
def _given_handler_fault(composition: G_CommitInterceptComposition) -> None:
    composition.inject_handler_fault()


@when("the SubagentStop hook processes the return")
def _when_hook_runs(
    composition: G_CommitInterceptComposition,
    outcome_holder: dict[str, InterceptOutcome],
) -> None:
    outcome_holder["result"] = composition.run_subagent_stop_hook()


@then(parsers.parse("the G_COMMIT intercept {outcome_phrase}"))
def _then_outcome(
    outcome_holder: dict[str, InterceptOutcome], outcome_phrase: str
) -> None:
    expected = GATE_OUTCOME_BY_PHRASE[outcome_phrase]
    assert outcome_holder["result"].outcome == expected


@then("the intercept records a verified slice commit in the ledger")
def _then_verified_recorded(outcome_holder: dict[str, InterceptOutcome]) -> None:
    assert outcome_holder["result"].ledger_event_for_slice == "SliceCommitVerified"


@then(parsers.parse("the intercept records {ledger_phrase} in the ledger"))
def _then_ledger_event(
    outcome_holder: dict[str, InterceptOutcome], ledger_phrase: str
) -> None:
    expected = {
        "a verified slice commit": "SliceCommitVerified",
        "a blocked slice commit": "SliceCommitBlocked",
    }[ledger_phrase]
    assert outcome_holder["result"].ledger_event_for_slice == expected


@then("the intercept reports an internal hook error")
def _then_internal_error(outcome_holder: dict[str, InterceptOutcome]) -> None:
    assert outcome_holder["result"].decision_event == "AtddPureHookInternalError"


@then("the hook exits with code zero")
def _then_exit_zero(outcome_holder: dict[str, InterceptOutcome]) -> None:
    assert outcome_holder["result"].exit_code == 0
