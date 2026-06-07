"""Unit tests for the M7 AT-completion ledger substrate (slice-03 / U3).

slice-03 of F-DES-ATDD-PURE-HOOK-GATES. The acceptance suite
(`tests/des/acceptance/atdd_pure_spine_hardening/`) drives the writer +
integrity-read; these unit tests cover the M4 reconciliation surface
(`carpaccio_gate_slices`, `verified_slices`, `reconcile_dispatch_count`) and the
M7(a) flock-serialised concurrent-append invariant -- behaviours the
acceptance ATs do not reach.

Port-to-port: the driving port is the `AtCompletionLedger` public API; the
ledger JSONL file on `tmp_path` is the observable surface.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from des.adapters.driven.logging.at_completion_ledger import (
    AtCompletionLedger,
    LedgerIntegrityViolation,
)


_CARPACCIO_CLEARED = "CarpaccioGateCleared"
_CARPACCIO_REJECTED = "CarpaccioGateRejected"
_SLICE_VERIFIED = "SliceCommitVerified"
_SLICE_BLOCKED = "SliceCommitBlocked"


def _ledger(tmp_path: Path) -> AtCompletionLedger:
    return AtCompletionLedger("demo-feature", tmp_path)


# --- M7(b): monotonic seq + record_hash on append ---------------------------


@given(event_count=st.integers(min_value=1, max_value=20))
@settings(max_examples=50, deadline=None)
def test_append_assigns_gap_free_monotonic_seq(
    tmp_path_factory: pytest.TempPathFactory, event_count: int
) -> None:
    """For any number of appends, seq is the gap-free sequence 1..N."""
    ledger = _ledger(tmp_path_factory.mktemp("ledger"))
    for index in range(event_count):
        ledger.append_gate_event(event=_CARPACCIO_CLEARED, slice_id=f"slice-{index}")

    records = ledger.read_records()
    assert [r["seq"] for r in records] == list(range(1, event_count + 1))
    assert all(isinstance(r["record_hash"], str) and r["record_hash"] for r in records)


def test_append_record_carries_event_and_slice(tmp_path: Path) -> None:
    """An appended record round-trips its event type and slice id."""
    ledger = _ledger(tmp_path)
    record = ledger.append_gate_event(event=_SLICE_VERIFIED, slice_id="slice-07")

    assert record["event"] == _SLICE_VERIFIED
    assert record["slice_id"] == "slice-07"
    assert record["seq"] == 1
    assert record["feature_id"] == "demo-feature"


# --- M7(c): fail-closed integrity read --------------------------------------


def test_absent_ledger_is_empty_not_a_violation(tmp_path: Path) -> None:
    """An absent ledger file reads as empty -- distinct from a corrupt one."""
    assert _ledger(tmp_path).read_records() == []


def test_seq_gap_raises_integrity_violation(tmp_path: Path) -> None:
    """A deleted middle record (seq gap) fails the read closed."""
    ledger = _ledger(tmp_path)
    for index in range(3):
        ledger.append_gate_event(event=_CARPACCIO_CLEARED, slice_id=f"slice-{index}")
    path = ledger.ledger_path()
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join([lines[0], lines[2]]) + "\n", encoding="utf-8")

    with pytest.raises(LedgerIntegrityViolation) as exc:
        ledger.read_records()
    assert exc.value.detail == "seq-gap"


def test_hash_tamper_raises_integrity_violation(tmp_path: Path) -> None:
    """A hand-edited field whose record_hash no longer matches fails closed."""
    ledger = _ledger(tmp_path)
    ledger.append_gate_event(event=_CARPACCIO_CLEARED, slice_id="slice-01")
    path = ledger.ledger_path()
    tampered = path.read_text(encoding="utf-8").replace("slice-01", "slice-99")
    path.write_text(tampered, encoding="utf-8")

    with pytest.raises(LedgerIntegrityViolation) as exc:
        ledger.read_records()
    assert exc.value.detail == "hash-mismatch"


def test_truncated_tail_raises_integrity_violation(tmp_path: Path) -> None:
    """A short final line (a killed append) fails the read closed."""
    ledger = _ledger(tmp_path)
    ledger.append_gate_event(event=_CARPACCIO_CLEARED, slice_id="slice-01")
    path = ledger.ledger_path()
    full = path.read_text(encoding="utf-8")
    path.write_text(full[: len(full) // 2], encoding="utf-8")

    with pytest.raises(LedgerIntegrityViolation) as exc:
        ledger.read_records()
    assert exc.value.detail == "truncated-tail"


# --- M4: dispatch-count reconciliation surface ------------------------------


@given(
    carpaccio_slices=st.sets(
        st.sampled_from(["slice-01", "slice-02", "slice-03", "slice-04"]),
        min_size=0,
        max_size=4,
    ),
    verified_slices=st.sets(
        st.sampled_from(["slice-01", "slice-02", "slice-03", "slice-04"]),
        min_size=0,
        max_size=4,
    ),
)
@settings(max_examples=50, deadline=None)
def test_reconciliation_surfaces_ungated_slices(
    tmp_path_factory: pytest.TempPathFactory,
    carpaccio_slices: set[str],
    verified_slices: set[str],
) -> None:
    """reconcile_dispatch_count returns exactly the entered-but-not-gated set.

    Invariant: a slice with a carpaccio gate event is reconciled away; a slice
    entered by the plan with no carpaccio event is surfaced as a discrepancy
    (the M4 R3-fix signal).
    """
    ledger = _ledger(tmp_path_factory.mktemp("ledger"))
    for slice_id in sorted(carpaccio_slices):
        ledger.append_gate_event(event=_CARPACCIO_CLEARED, slice_id=slice_id)
    for slice_id in sorted(verified_slices):
        ledger.append_gate_event(event=_SLICE_VERIFIED, slice_id=slice_id)

    entered = frozenset(["slice-01", "slice-02", "slice-03", "slice-04"])

    assert ledger.carpaccio_gate_slices() == carpaccio_slices
    assert ledger.verified_slices() == verified_slices
    assert ledger.reconcile_dispatch_count(entered) == entered - carpaccio_slices


def test_rejected_carpaccio_event_counts_as_gated(tmp_path: Path) -> None:
    """A rejected gate still counts -- the slice WAS gated, just not cleared."""
    ledger = _ledger(tmp_path)
    ledger.append_gate_event(event=_CARPACCIO_REJECTED, slice_id="slice-01")

    assert ledger.carpaccio_gate_slices() == frozenset(["slice-01"])
    assert ledger.reconcile_dispatch_count(frozenset(["slice-01"])) == frozenset()


def test_blocked_slice_commit_is_not_a_verified_slice(tmp_path: Path) -> None:
    """A SliceCommitBlocked record does not count toward verified slices."""
    ledger = _ledger(tmp_path)
    ledger.append_gate_event(event=_SLICE_BLOCKED, slice_id="slice-01")

    assert ledger.verified_slices() == frozenset()


# --- M7(a): flock-serialised concurrent append ------------------------------


def test_concurrent_appends_serialise_without_seq_collision(tmp_path: Path) -> None:
    """Concurrent appender processes serialise -- no seq collision, no gap.

    Spawns N child processes each appending one record; the flock makes the
    read-seq -> write critical section atomic. The resulting ledger passes the
    integrity read with a gap-free 1..N sequence.
    """
    from concurrent.futures import ProcessPoolExecutor

    ledger_root = str(tmp_path)
    worker_count = 8

    with ProcessPoolExecutor(max_workers=worker_count) as pool:
        list(
            pool.map(
                _append_one_record,
                [(ledger_root, i) for i in range(worker_count)],
            )
        )

    records = _ledger(tmp_path).read_records()
    assert [r["seq"] for r in records] == list(range(1, worker_count + 1))


def _append_one_record(args: tuple[str, int]) -> None:
    """Worker entry point -- append exactly one record to the shared ledger."""
    ledger_root, index = args
    AtCompletionLedger("demo-feature", Path(ledger_root)).append_gate_event(
        event=_CARPACCIO_CLEARED, slice_id=f"slice-{index}"
    )
