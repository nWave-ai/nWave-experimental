"""Composition root for slice-03 -- the M7 AT-completion ledger substrate.

slice-03 of F-DES-ATDD-PURE-HOOK-GATES (U3 -- ADR-030 D3 / M7).

Wires the PRODUCTION ledger substrate:
  * `des.adapters.driven.logging.at_completion_ledger.AtCompletionLedger` --
    the integrity-checked writer/reader: flock-serialised append, per-record
    monotonic `seq` + `record_hash`, fail-closed integrity read.
  * `des.adapters.driven.logging.at_completion_ledger.LedgerIntegrityViolation`
    -- the fail-closed exception the U1 order check and U4 feature-end gate
    surface as a block.

The driving port is the `AtCompletionLedger` class. The only real I/O is the
ledger JSONL file under a tmp `.nwave/telemetry/atdd-pure/` directory -- a
layer-3 subprocess/FS acceptance surface (example-only, Mandate 9/11).

Business logic lives in the production module; step bodies delegate to
`LedgerComposition` methods and never inline logic (Mandate-12 criterion 3).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import (
    AtCompletionLedger,
    LedgerIntegrityViolation,
)

from .domain_types import (
    FeatureId,
    GateEvent,
    LedgerCorruption,
    ReadVerdict,
    SliceId,
)


_FEATURE_ID = FeatureId("atdd-pure-demo")


@dataclass
class ReadOutcome:
    """The observable result of an integrity-checked ledger read."""

    verdict: ReadVerdict
    verified_slices: frozenset[str]
    seq_gap_free: bool
    every_record_hashed: bool


class LedgerComposition:
    """Production-wired composition root for the M7 ledger substrate slice.

    The driving port is the `AtCompletionLedger` class; the observable surface
    is the integrity-checked read verdict plus the reconstructed slice state.
    """

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root
        self._feature_id = _FEATURE_ID
        self._ledger = AtCompletionLedger(self._feature_id, project_root)
        self._provision_dir = True

    # --- ledger provisioning ------------------------------------------------

    def use_fresh_ledger(self) -> None:
        """Start from a fresh ledger -- the telemetry directory exists, empty."""
        self._ledger.ledger_dir().mkdir(parents=True, exist_ok=True)

    def use_unprovisioned_feature(self) -> None:
        """Start from a feature whose ledger directory does not yet exist."""
        # No directory creation here -- the first append must provision it.
        assert not self._ledger.ledger_dir().exists()

    # --- gate-event recording (the M4 emission surface) ---------------------

    def record_gate_event(self, event: GateEvent, slice_id: SliceId) -> None:
        """Append one gate-boundary audit record into the integrity ledger."""
        self._ledger.append_gate_event(event=event.value, slice_id=slice_id)

    def record_three_events(self) -> None:
        """Append three well-formed gate events -- the corruption-test baseline."""
        self.use_fresh_ledger()
        self._ledger.append_gate_event(
            event=GateEvent.CARPACCIO_GATE_CLEARED.value, slice_id=SliceId("slice-01")
        )
        self._ledger.append_gate_event(
            event=GateEvent.SLICE_COMMIT_VERIFIED.value, slice_id=SliceId("slice-01")
        )
        self._ledger.append_gate_event(
            event=GateEvent.CARPACCIO_GATE_CLEARED.value, slice_id=SliceId("slice-02")
        )

    # --- corruption injection (the M7 integrity universe) -------------------

    def corrupt_ledger(self, corruption: LedgerCorruption) -> None:
        """Mutate the ledger file to model one M7 integrity-violation case."""
        if corruption is LedgerCorruption.NONE:
            return
        path = self._ledger.ledger_path()
        lines = path.read_text(encoding="utf-8").splitlines()
        if corruption is LedgerCorruption.MALFORMED:
            lines[1] = "{not valid json"
        elif corruption is LedgerCorruption.TRUNCATED:
            lines[-1] = lines[-1][: len(lines[-1]) // 2]
        elif corruption is LedgerCorruption.HASH_MISMATCH:
            lines[1] = lines[1].replace('"slice-01"', '"slice-01-tampered"', 1)
        elif corruption is LedgerCorruption.SEQ_GAP:
            # Drop the middle record -> the seq sequence gains a gap.
            lines = [lines[0], lines[2]]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # --- driving-port invocations -------------------------------------------

    def read_under_integrity_contract(self) -> ReadOutcome:
        """Read the ledger under the M7 fail-closed integrity contract."""
        try:
            records = self._ledger.read_records()
        except LedgerIntegrityViolation:
            return ReadOutcome(
                verdict=ReadVerdict.BLOCKED,
                verified_slices=frozenset(),
                seq_gap_free=False,
                every_record_hashed=False,
            )
        verified = frozenset(
            str(r["slice_id"])
            for r in records
            if r["event"] == GateEvent.SLICE_COMMIT_VERIFIED.value
        )
        seqs = [int(r["seq"]) for r in records]
        gap_free = seqs == list(range(seqs[0], seqs[0] + len(seqs))) if seqs else True
        all_hashed = all(
            isinstance(r.get("record_hash"), str) and r["record_hash"] for r in records
        )
        return ReadOutcome(
            verdict=ReadVerdict.OK,
            verified_slices=verified,
            seq_gap_free=gap_free,
            every_record_hashed=all_hashed,
        )

    def ledger_directory_exists(self) -> bool:
        """Whether the first append provisioned the telemetry directory (M11)."""
        return self._ledger.ledger_dir().is_dir()
