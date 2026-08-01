"""ReductionKeyDeduper + Aggregate -- DD-7/DD-8/DD-9 (unified-event-store
slice-03).

`ReductionKeyDeduper.dedupe()` is implemented (DELIVER slice-03). `Aggregate`
is declared right here, beside its sole producer -- unlike `EventRecord`/
`AppendedRecord`/`ReadResult`, which live in the port module
`event_store_port.py` because callers construct/consume them directly.

Design contract (feature-delta.md DD-7, DD-8, DD-9, [REF] Architecture &
Contract Tests row `test_event_store_aggregate.py`):

* DD-7 -- DERIVED records carry `reduction_key`/`reduction_seq`/
  `reduced_through_request`/`reducer_version`; the read rule is
  MAX(`reduction_seq`) per `reduction_key`. Within one key's group, exactly
  the single record with the highest `reduction_seq` is measured; older
  duplicates are silently superseded (NOT counted as could-not-verify --
  supersession is not the same failure class as dedup-ineligibility).
* DD-8 -- `reduction_key` requires a non-null `agent_id`. A record whose
  `agent_id` is null is dedup-ineligible: it NEVER participates in a
  MAX(reduction_seq) group (never "MAX'd away" -- i.e. never silently
  discarded as if it lost a comparison it was never eligible to enter), and
  it is counted `could_not_verify`, never `measured`, regardless of what
  `reduction_seq` it carries. This is re-verified at READ time by
  `ReductionKeyDeduper` independently of whatever the write path
  (`UnifiedEventStoreAdapter.append_derived`) already enforced -- a reader
  must never trust that every stored record already satisfies DD-8.
* DD-9 -- every aggregate result is an `Aggregate`, never a bare `int`:
  `measured_count`, `could_not_verify_count`, `could_not_verify_reasons` are
  ALL present, always, with the arity invariant
  `could_not_verify_count == len(could_not_verify_reasons)`.
* An AMBIGUOUS group -- two eligible records sharing one `reduction_key` AND
  the same maximum `reduction_seq` -- is reported `could_not_verify`, never
  resolved by silently picking one (the same "never silently collapse an
  unproven identity" rule DD-8 states for null `agent_id`, applied to a tie).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = ["Aggregate", "ReductionKeyDeduper"]


@dataclass(frozen=True)
class Aggregate:
    """The arity-safe rollup DD-9 requires every read/aggregate to return.

    `could_not_verify_count` and `could_not_verify_reasons` are REQUIRED
    fields (no zero-omitting default a caller forgets to read) -- a caller
    cannot construct an `Aggregate` that silently drops the could-not-verify
    axis. `could_not_verify_reasons` defaults to an empty list ONLY at
    construction convenience for the trivial all-measured case; the count
    field itself is still mandatory and must equal `len(reasons)`.
    """

    measured_count: int
    could_not_verify_count: int
    could_not_verify_reasons: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Enforce the DD-9 arity invariant STRUCTURALLY -- by construction,
        not merely by a test observing it after the fact (GDP-8)."""
        if self.could_not_verify_count != len(self.could_not_verify_reasons):
            raise ValueError(
                "WHAT: Aggregate.could_not_verify_count="
                f"{self.could_not_verify_count!r} does not equal "
                f"len(could_not_verify_reasons)={len(self.could_not_verify_reasons)!r}. "
                "WHY: DD-9's arity invariant requires the count and its "
                "reasons to travel together exactly -- a mismatch would let "
                "the could-not-verify axis silently drift from its own "
                "evidence. "
                "HOW: pass a could_not_verify_count equal to the number of "
                "reasons in could_not_verify_reasons."
            )


class ReductionKeyDeduper:
    """Pure, side-effect-free DD-7/DD-8 reduction over derived records.

    No constructor state -- `dedupe` is a pure function of its argument.
    """

    @staticmethod
    def dedupe(records: Sequence[Mapping[str, Any]]) -> Aggregate:
        """Apply MAX(reduction_seq) per reduction_key (DD-7), routing any
        null-agent_id record to could_not_verify (DD-8) and any ambiguous
        (tied-max) group to could_not_verify as well.
        """
        eligible_groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        could_not_verify_reasons: list[str] = []

        for record in records:
            reduction_key = record["reduction_key"]
            if record["agent_id"] is None:
                could_not_verify_reasons.append(
                    f"null agent_id for reduction_key={reduction_key!r} "
                    f"(reduction_seq={record['reduction_seq']!r}) -- DD-8 "
                    "dedup-ineligible"
                )
                continue
            eligible_groups[reduction_key].append(record)

        measured_count = 0
        for reduction_key, group in eligible_groups.items():
            max_seq = max(r["reduction_seq"] for r in group)
            winners = [r for r in group if r["reduction_seq"] == max_seq]
            if len(winners) == 1:
                measured_count += 1
            else:
                could_not_verify_reasons.append(
                    f"ambiguous tied-max reduction_seq={max_seq!r} for "
                    f"reduction_key={reduction_key!r} ({len(winners)} "
                    "records tied)"
                )

        return Aggregate(
            measured_count=measured_count,
            could_not_verify_count=len(could_not_verify_reasons),
            could_not_verify_reasons=could_not_verify_reasons,
        )
