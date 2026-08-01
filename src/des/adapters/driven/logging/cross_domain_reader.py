"""CrossDomainReader -- merges N per-family JSONL ledgers into one sorted,
provenance-tagged timeline (D80 DD-13, unified-event-store slice-04).

Design contract (feature-delta.md DD-13, [REF] Component Decomposition C4
L2/L3, [REF] Driving Ports `read_across` row): merges the per-family JSONL
files `telemetry_paths.ledger_path(project_root, family, partition_key)`
resolves for each of `families`, for the SAME `partition_key`, into one
`ReadResult` sorted by `(timestamp, seq)` ascending, with each row tagged
with its source family (a NEW overlay key on a copy of the row -- never a
physical rewrite of the file it read, same non-mutation discipline as
`LegacyEnvelopeNormalizer.normalize()`). `could_not_verify_count` /
`could_not_verify_reasons` (DD-9 arity) accumulate across every family
read, never reset per-family and never silently dropped. An absent
per-family ledger file is zero records from that family, not a
could-not-verify condition -- consumer #4's whole point is a timeline that
is honest about ABSENCE OF EVIDENCE vs a broken read.

`read_across`'s declared sort key is `(timestamp, seq)` (feature-delta.md
[REF] Driving Ports). This only produces a correct merge once EVERY family
stamps `seq` -- today `record_examine_verdict.py` / `record_review_verdict.py`
are hand-rolled writers that do not (Reuse Analysis row 3); their migration
onto `AtCompletionLedger.append_event` is this same slice's other Owns
item, so DELIVER must land both together, not `read_across` alone.

DELIVER wiring (this module):

* Per-family row RECOGNITION (row-shape/type gates, legacy normalization,
  ADR-EVT-002 deny-by-default) is REUSED verbatim from
  `UnifiedEventStoreAdapter.read()` -- never re-implemented here, so the
  contract cannot drift between the single-family and cross-domain paths.
  A family whose ledger file does not exist at all is skipped BEFORE
  calling `read()` (the ONLY family-level distinction this module adds):
  `read()` itself treats an absent file as `could_not_verify` (correct for
  its own single-family contract), but DD-13's cross-domain contract is
  the opposite for that same condition -- an absent family contributes
  zero records, not a could-not-verify.
* `read()`'s own `ReadResult.records` is the RAW row population (legacy +
  primary-new + every row that passed the derived-branch type gate,
  UNCOLLAPSED by reduction_key -- `read()`'s `measured_count` already
  reflects the DD-7 collapse, but its `records` list intentionally does
  not, per its own module docstring). `read_across` materializes a
  timeline of DISTINCT events, so `_collapse_shared_reduction_keys`
  applies DD-7's MAX(reduction_seq)-per-key winner selection (mirroring
  `ReductionKeyDeduper.dedupe`'s eligibility + tie rules) to pick exactly
  one row per group for the merged list -- the COUNTS themselves are never
  recomputed here, only reused from `read()`.
* `_timestamp_fault_reason` is new validation `read()` has no reason to
  perform (a single-family read never sorts): `read_across`'s declared
  sort key needs a well-typed `timestamp` on every row, so a missing or
  wrong-typed `timestamp` degrades into its own NAMED could_not_verify
  reason (DD-17 deny-by-default, applied to the ordering key) rather than
  crashing the sort or ordering arbitrarily.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from des.adapters.driven.logging.unified_event_store_adapter import (
    UnifiedEventStoreAdapter,
)
from des.domain.telemetry_paths import ledger_path
from des.ports.driven_ports.event_store_port import ReadResult


if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from des.domain.telemetry_paths import LedgerFamily


__all__ = ["CrossDomainReader"]


class CrossDomainReader:
    """Merges N `LedgerFamily` JSONL ledgers for one `partition_key` (DD-13).

    Constructed with the target repo's `project_root`, mirroring
    `UnifiedEventStoreAdapter` / `StoreAvailabilityProbe`'s own construction
    shape (component decomposition C4 L2) -- no shared state with either;
    a plain reader over the filesystem.
    """

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root

    def read_across(
        self, families: Sequence[LedgerFamily], partition_key: str
    ) -> ReadResult:
        adapter = UnifiedEventStoreAdapter(self._project_root)
        tagged_rows: list[dict[str, Any]] = []
        could_not_verify_count = 0
        could_not_verify_reasons: list[str] = []

        for family in families:
            path = ledger_path(self._project_root, family, partition_key)
            if not path.is_file():
                # DD-13: an absent per-family ledger is zero records from
                # that family, never a could_not_verify (distinct from
                # read()'s own single-family contract for the same fact).
                continue

            result = adapter.read(family, partition_key)
            could_not_verify_count += result.could_not_verify_count
            could_not_verify_reasons.extend(result.could_not_verify_reasons)
            for row in result.records:
                tagged = dict(row)
                tagged["_source_family"] = family.value
                tagged_rows.append(tagged)

        deduped_rows = self._collapse_shared_reduction_keys(tagged_rows)

        ordered_rows: list[dict[str, Any]] = []
        for row in deduped_rows:
            fault = self._timestamp_fault_reason(row) or self._seq_fault_reason(row)
            if fault is not None:
                could_not_verify_count += 1
                could_not_verify_reasons.append(fault)
                continue
            ordered_rows.append(row)

        ordered_rows.sort(key=lambda row: (row["timestamp"], row.get("seq", 0)))

        return ReadResult(
            records=ordered_rows,
            measured_count=len(ordered_rows),
            could_not_verify_count=could_not_verify_count,
            could_not_verify_reasons=could_not_verify_reasons,
        )

    @staticmethod
    def _collapse_shared_reduction_keys(
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Materialize exactly one row per `reduction_key` group (DD-7's
        MAX(reduction_seq) winner) so the merged timeline conserves
        DISTINCT events, never raw ledger lines. Mirrors the SAME
        eligibility (DD-8 null-`agent_id`) and winner-selection rule
        `ReductionKeyDeduper.dedupe` already applies at the count layer --
        the counts themselves are reused verbatim from `read()` above, this
        only selects WHICH row represents a group in the materialized
        timeline. A row with no `reduction_key` key at all (legacy or
        primary-new) passes through unchanged.
        """
        passthrough: list[dict[str, Any]] = []
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            reduction_key = row.get("reduction_key")
            if reduction_key is None:
                passthrough.append(row)
                continue
            groups.setdefault(reduction_key, []).append(row)

        winners: list[dict[str, Any]] = []
        for group in groups.values():
            eligible = [row for row in group if row.get("agent_id") is not None]
            if not eligible:
                # DD-8: null-agent_id rows are dedup-ineligible -- already
                # excluded from read()'s measured_count; omit from display.
                continue
            max_seq = max(row["reduction_seq"] for row in eligible)
            candidates = [row for row in eligible if row["reduction_seq"] == max_seq]
            if len(candidates) == 1:
                winners.append(candidates[0])
            # an ambiguous tied-max group is already could_not_verify-
            # counted by read()'s own Aggregate; omit from display rather
            # than silently pick one.

        return [*passthrough, *winners]

    @staticmethod
    def _timestamp_fault_reason(row: dict[str, Any]) -> str | None:
        """R56/R57: `read_across`'s own declared sort key `(timestamp,
        seq)` requires a well-typed `timestamp` on every merged row --
        missing and wrong-typed are two DISTINCT, separately-named reasons
        (never a generic 'could not verify')."""
        source_family = row.get("_source_family")
        event = row.get("event")
        if "timestamp" not in row:
            return (
                f"row for event={event!r} from family={source_family!r} "
                "is missing its timestamp field entirely -- absent, never "
                "silently ordered"
            )
        timestamp = row["timestamp"]
        if not isinstance(timestamp, str):
            return (
                f"row for event={event!r} from family={source_family!r} "
                f"has a timestamp of type {type(timestamp).__name__} "
                f"({timestamp!r}) -- admissible type is str, not a number"
            )
        return None

    @staticmethod
    def _seq_fault_reason(row: dict[str, Any]) -> str | None:
        """R58: `read_across`'s declared sort key `(timestamp, seq)` also
        needs a well-typed `seq` on any row that carries one -- `seq`
        itself is OPTIONAL (R59: an absent `seq` sorts as 0 and stays a
        legitimate measured record, DD-17 deny-by-default applies to the
        VALUE's type, never to its presence). Only a PRESENT, wrong-typed
        `seq` degrades this one row into its own NAMED could_not_verify
        reason -- naming `seq`, never `timestamp`, so it stays
        distinguishable from R56/R57 even though all three share the same
        ordering key."""
        if "seq" not in row:
            return None
        seq = row["seq"]
        if isinstance(seq, int):
            return None
        source_family = row.get("_source_family")
        event = row.get("event")
        return (
            f"row for event={event!r} from family={source_family!r} "
            f"has a seq of type {type(seq).__name__} "
            f"({seq!r}) -- admissible type is int, not {type(seq).__name__}"
        )
