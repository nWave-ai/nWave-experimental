"""Step definitions for slice-01 -- the `des emit-feature-end` CLI.

slice-01 of oss-feature-end-emit-cli (the R2 walking-skeleton).

Step bodies are delegate-only (Mandate-12 criterion 3): each is a single typed
lookup / one `EmitFeatureEndComposition` call + one observable assertion. All
emit logic lives in the production `des emit-feature-end` subcommand; the
composition root only wires the real subprocess and reads back the completion
ledger substrate the done-gate consumes.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition import EmitFeatureEndComposition, EmitResult
from .domain_types import EmitOutcome, FeatureEndRecord


scenarios("../slice-01-feature-end-emit.feature")


@pytest.fixture
def composition(tmp_path: Path) -> EmitFeatureEndComposition:
    return EmitFeatureEndComposition(tmp_path)


@pytest.fixture
def result_holder() -> dict[str, EmitResult]:
    return {}


# --- Given --------------------------------------------------------------------


@given("an orchestrator at the feature-end of a feature")
def _given_feature_end(composition: EmitFeatureEndComposition) -> None:
    # The feature-end precondition is an empty completion ledger -- no
    # feature-end record has been emitted yet. The tmp_path working tree is the
    # whole precondition; no fixture pre-writes the expected output.
    assert (
        composition.ledger_has_record(FeatureEndRecord.BATCH_REFACTOR_COMPLETED)
        is False
    )
    assert composition.ledger_has_record(FeatureEndRecord.DEEP_REVIEW_VERDICT) is False


# --- When ---------------------------------------------------------------------


@when("the orchestrator records that the batch refactor completed")
def _when_emit_batch_refactor(
    composition: EmitFeatureEndComposition,
    result_holder: dict[str, EmitResult],
) -> None:
    result_holder["result"] = composition.emit_record(
        FeatureEndRecord.BATCH_REFACTOR_COMPLETED
    )


@when("the orchestrator records the deep-review verdict with its signed hash")
def _when_emit_verdict_with_hash(
    composition: EmitFeatureEndComposition,
    result_holder: dict[str, EmitResult],
) -> None:
    result_holder["result"] = composition.emit_record(
        FeatureEndRecord.DEEP_REVIEW_VERDICT,
        verdict_hash=composition.signed_verdict_hash,
    )


@when("the orchestrator records the deep-review verdict without a signed hash")
def _when_emit_verdict_without_hash(
    composition: EmitFeatureEndComposition,
    result_holder: dict[str, EmitResult],
) -> None:
    result_holder["result"] = composition.emit_record(
        FeatureEndRecord.DEEP_REVIEW_VERDICT
    )


@when(
    "the orchestrator records the batch-refactor completion with a signed verdict hash"
)
def _when_emit_batch_refactor_with_hash(
    composition: EmitFeatureEndComposition,
    result_holder: dict[str, EmitResult],
) -> None:
    result_holder["result"] = composition.emit_record(
        FeatureEndRecord.BATCH_REFACTOR_COMPLETED,
        verdict_hash=composition.signed_verdict_hash,
    )


# --- Then ---------------------------------------------------------------------


@then("the completion ledger carries the batch-refactor-completed record")
def _then_ledger_has_batch_refactor(composition: EmitFeatureEndComposition) -> None:
    assert (
        composition.ledger_has_record(FeatureEndRecord.BATCH_REFACTOR_COMPLETED) is True
    )


@then("the completion ledger carries the deep-review-verdict record")
def _then_ledger_has_verdict(composition: EmitFeatureEndComposition) -> None:
    assert composition.ledger_has_record(FeatureEndRecord.DEEP_REVIEW_VERDICT) is True


@then("the deep-review-verdict record carries the signed hash")
def _then_verdict_carries_hash(composition: EmitFeatureEndComposition) -> None:
    assert composition.recorded_verdict_hash(
        FeatureEndRecord.DEEP_REVIEW_VERDICT
    ) == str(composition.signed_verdict_hash)


@then("the command reports success")
def _then_command_succeeds(result_holder: dict[str, EmitResult]) -> None:
    assert result_holder["result"].outcome == EmitOutcome.SUCCEEDED


@then("the command refuses the record")
def _then_command_refuses(result_holder: dict[str, EmitResult]) -> None:
    assert result_holder["result"].outcome == EmitOutcome.REFUSED


@then("the completion ledger carries no deep-review-verdict record")
def _then_ledger_has_no_verdict(composition: EmitFeatureEndComposition) -> None:
    assert composition.ledger_has_record(FeatureEndRecord.DEEP_REVIEW_VERDICT) is False


@then("the completion ledger carries no batch-refactor-completed record")
def _then_ledger_has_no_batch_refactor(composition: EmitFeatureEndComposition) -> None:
    assert (
        composition.ledger_has_record(FeatureEndRecord.BATCH_REFACTOR_COMPLETED)
        is False
    )
