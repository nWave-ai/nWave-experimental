"""Step definitions for slice-01 -- the G-DISTILL-EXIT SubagentStop gate.

slice-01 of oss-hook-side-phase-injection (the DISTILL-wave hook keystone, D1).

Step bodies are delegate-only (Mandate-12 criterion 3): each is a single typed
lookup into the ``domain_types`` phrase tables plus one
``DistillExitGateComposition`` call. All gate logic lives in the production
SubagentStop handler; the composition root only wires the real hook subprocess
and seeds / reads the precondition ledger substrate.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition import DistillExitGateComposition, DistillExitOutcome
from .domain_types import (
    BLOCK_EVENT_BY_PHRASE,
    GateOutcome,
    SlicePlanShape,
    VerdictSetShape,
)


scenarios("../g-distill-exit-gate.feature")


@pytest.fixture
def composition(tmp_path: Path) -> DistillExitGateComposition:
    comp = DistillExitGateComposition(tmp_path)
    comp.init_repo()
    return comp


@pytest.fixture
def outcome_holder() -> dict[str, DistillExitOutcome]:
    return {}


# --- Given --------------------------------------------------------------------


@given("a DISTILL feature whose plan declares every slice")
def _given_plan_present(composition: DistillExitGateComposition) -> None:
    composition.write_slice_plan(SlicePlanShape.PRESENT)


@given("a DISTILL feature whose plan cannot be read")
def _given_plan_unparseable(composition: DistillExitGateComposition) -> None:
    composition.write_slice_plan(SlicePlanShape.UNPARSEABLE)


@given("every planned slice has a signed acceptance-test review")
def _given_verdicts_complete(composition: DistillExitGateComposition) -> None:
    composition.seed_verdict_set(VerdictSetShape.COMPLETE)


@given("every planned slice except one has a signed acceptance-test review")
def _given_verdicts_missing_one(composition: DistillExitGateComposition) -> None:
    composition.seed_verdict_set(VerdictSetShape.MISSING_ONE)


@given("the acceptance designer returns from the DISTILL phase")
def _given_distill_return(composition: DistillExitGateComposition) -> None:
    composition.write_distill_return_transcript()


# --- When ---------------------------------------------------------------------


@when("the SubagentStop hook processes the return")
def _when_hook_runs(
    composition: DistillExitGateComposition,
    outcome_holder: dict[str, DistillExitOutcome],
) -> None:
    outcome_holder["result"] = composition.run_subagent_stop_hook()


# --- Then ---------------------------------------------------------------------


@then("the DISTILL-exit gate allows the transition")
def _then_allows(outcome_holder: dict[str, DistillExitOutcome]) -> None:
    assert outcome_holder["result"].outcome == GateOutcome.ALLOWED


@then(parsers.parse("the DISTILL-exit gate reports {block_phrase}"))
def _then_blocks_with_event(
    outcome_holder: dict[str, DistillExitOutcome], block_phrase: str
) -> None:
    expected_event = BLOCK_EVENT_BY_PHRASE[block_phrase]
    result = outcome_holder["result"]
    assert result.outcome == GateOutcome.BLOCKED
    assert result.decision_event == expected_event


@then("a DISTILL phase-completed record is written to the ledger")
def _then_phase_completed_present(
    outcome_holder: dict[str, DistillExitOutcome],
) -> None:
    assert outcome_holder["result"].phase_completed_emitted is True


@then("no DISTILL phase-completed record is written to the ledger")
def _then_phase_completed_absent(
    outcome_holder: dict[str, DistillExitOutcome],
) -> None:
    assert outcome_holder["result"].phase_completed_emitted is False


@then("the hook exits with code zero")
def _then_exit_zero(outcome_holder: dict[str, DistillExitOutcome]) -> None:
    assert outcome_holder["result"].exit_code == 0
