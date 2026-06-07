"""Unit tests for the F1 feature-end ledger records (slice-05 revision).

slice-05 of F-DES-ATDD-PURE-HOOK-GATES -- closes deep-review Finding 1.

The U4 feature-end gate previously passed merely on the AT-completion ledger
file being present + every planned slice carrying a `SliceCommitVerified`
record. A feature with zero refactor + zero deep review passed U4. Finding 1
requires the feature-end *cycle* to write two machine records:

  * `EBatchRefactorCompleted`  -- the E_BATCH_REFACTOR phase ran.
  * `FeatureEndReviewVerdict`  -- the feature-end deep review ran; the record
                                  carries the reviewer `verdict_hash`.

`_handle_feature_end_gate` and `verify_deliver_integrity._verify_atdd_pure`
assert BOTH are present before feature-end passes; absent either ->
`FeatureEndCycleIncomplete` fail-closed block.

These records are feature-scoped (no slice). They ride the same M7 integrity
substrate -- `seq` + `record_hash`, flock append, fail-closed read.

Port-to-port: the driving port is `AtCompletionLedger.append_feature_end_event`
and `feature_end_events`; the ledger JSONL file is the observable surface.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import (
    AtCompletionLedger,
    LedgerIntegrityViolation,
)


_E_BATCH_REFACTOR = "EBatchRefactorCompleted"
_FEATURE_END_VERDICT = "FeatureEndReviewVerdict"


def _ledger(tmp_path: Path) -> AtCompletionLedger:
    return AtCompletionLedger("demo-feature", tmp_path)


# --- F1: feature-end record append ------------------------------------------


def test_append_feature_end_event_round_trips(tmp_path: Path) -> None:
    """An EBatchRefactorCompleted record round-trips its event type."""
    ledger = _ledger(tmp_path)
    record = ledger.append_feature_end_event(event=_E_BATCH_REFACTOR)

    assert record["event"] == _E_BATCH_REFACTOR
    assert record["seq"] == 1
    assert record["feature_id"] == "demo-feature"
    assert record["slice_id"] == ""  # feature-scoped, no slice
    assert isinstance(record["record_hash"], str) and record["record_hash"]


def test_feature_end_verdict_record_carries_verdict_hash(tmp_path: Path) -> None:
    """A FeatureEndReviewVerdict record carries the reviewer verdict_hash."""
    ledger = _ledger(tmp_path)
    record = ledger.append_feature_end_event(
        event=_FEATURE_END_VERDICT, verdict_hash="abc123def456"
    )

    assert record["event"] == _FEATURE_END_VERDICT
    assert record["verdict_hash"] == "abc123def456"


def test_feature_end_events_reads_back_the_recorded_events(tmp_path: Path) -> None:
    """feature_end_events returns the set of feature-end event names recorded."""
    ledger = _ledger(tmp_path)
    assert ledger.feature_end_events() == frozenset()

    ledger.append_feature_end_event(event=_E_BATCH_REFACTOR)
    ledger.append_feature_end_event(event=_FEATURE_END_VERDICT, verdict_hash="hash-xyz")

    assert ledger.feature_end_events() == frozenset(
        {_E_BATCH_REFACTOR, _FEATURE_END_VERDICT}
    )


def test_verdict_hash_is_hashed_into_record_hash(tmp_path: Path) -> None:
    """Tampering with verdict_hash breaks the M7 record_hash integrity check."""
    ledger = _ledger(tmp_path)
    ledger.append_feature_end_event(
        event=_FEATURE_END_VERDICT, verdict_hash="original-hash"
    )
    path = ledger.ledger_path()
    tampered = path.read_text(encoding="utf-8").replace("original-hash", "forged-hash")
    path.write_text(tampered, encoding="utf-8")

    with pytest.raises(LedgerIntegrityViolation) as exc:
        ledger.read_records()
    assert exc.value.detail == "hash-mismatch"


def test_feature_end_events_coexist_with_slice_records(tmp_path: Path) -> None:
    """Feature-end records and slice gate records share one integrity-checked log."""
    ledger = _ledger(tmp_path)
    ledger.append_gate_event(event="SliceCommitVerified", slice_id="slice-01")
    ledger.append_feature_end_event(event=_E_BATCH_REFACTOR)
    ledger.append_gate_event(event="SliceCommitVerified", slice_id="slice-02")
    ledger.append_feature_end_event(event=_FEATURE_END_VERDICT, verdict_hash="h")

    records = ledger.read_records()
    assert [r["seq"] for r in records] == [1, 2, 3, 4]
    assert ledger.verified_slices() == frozenset({"slice-01", "slice-02"})
    assert ledger.feature_end_events() == frozenset(
        {_E_BATCH_REFACTOR, _FEATURE_END_VERDICT}
    )
