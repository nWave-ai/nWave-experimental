"""Parallel-safety value types + the pure pairwise-disjointness classifier.

Feature-delta: docs/feature/measured-parallel-safety-report/feature-delta.md
  ([REF] DDD List, [REF] Decisions Table DD/DG, [REF] Contract Tests CT-1..CT-5).

Pure, side-effect-free value types + a pure classifier -- zero coupling to
`des.*` (Effect Isolation, principle 12; mirrors `domain/blast_radius.py`).

Core domain invariant (D-4 made structural): `classify_pair` takes TWO real
`SliceMeasurement`s and its codomain is exactly `{MEASURED-SAFE, DRIFT}`.
`UNMEASURED` is NOT in its codomain -- it arises ONLY from a missing
measurement (`SliceUnmeasured`), upstream of classification. "Honest
do-not-know is never coerced to a safe/unsafe verdict" is thus
non-representable in the type system, not merely tested-around.

Disjointness rule (DD): two measurements are DISJOINT iff their touched-files,
boundary-files, and consumer-symbol sets are pairwise empty-intersection;
overlap on ANY of the three axes is DRIFT (mirrors blast-radius's "L iff ANY").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ParallelSafetyVerdict(str, Enum):
    """The measured verdict on a declared-parallel pair.

    The classifier's codomain is exactly these two (D-4/DG): a real
    measurement is either measurably disjoint (SAFE) or measurably overlapping
    (DRIFT). UNMEASURED is deliberately ABSENT -- it can never be reached from
    two real measurements.
    """

    MEASURED_SAFE = "MEASURED-SAFE"
    DRIFT = "DRIFT"


@dataclass(frozen=True)
class SliceMeasurement:
    """The measured blast radius of ONE declared-parallel slice's scope.

    `files` is the report-supplied touched-file set (the `--paths` axis, DB);
    `boundary_files` and `consumer_symbols` come from `des blast-radius`. All
    three are the disjointness axes classified in `classify_pair`.
    """

    slice_id: str
    files: frozenset[str] = field(default_factory=frozenset)
    boundary_files: frozenset[str] = field(default_factory=frozenset)
    consumer_symbols: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class SliceUnmeasured:
    """An honest do-not-know for ONE slice (D-4): a measurement was not taken.

    Lives ONLY in the port return type, upstream of `classify_pair` -- it is
    structurally impossible for a `SliceUnmeasured` to become a SAFE/DRIFT
    verdict. Names the slice + the scope paths it could not measure + why.
    """

    slice_id: str
    paths: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class PairOverlap:
    """The measured overlap between two slices, per axis. Empty on all three
    axes iff the pair is disjoint (MEASURED-SAFE)."""

    files: tuple[str, ...] = ()
    boundary_files: tuple[str, ...] = ()
    consumer_symbols: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        """True iff there is no overlap on any of the three axes (disjoint)."""
        return not (self.files or self.boundary_files or self.consumer_symbols)


@dataclass(frozen=True)
class PairClassification:
    """The verdict on a pair: `{MEASURED-SAFE, DRIFT}` + the naming overlap +
    the reasons that fired (never a bare verdict token, GDP-3)."""

    verdict: ParallelSafetyVerdict
    overlap: PairOverlap
    reasons: tuple[str, ...]


def classify_pair(a: SliceMeasurement, b: SliceMeasurement) -> PairClassification:
    """Classify two real measurements as MEASURED-SAFE or DRIFT (never
    UNMEASURED -- D-4/DG structural). Pure.

    DRIFT iff the pair overlaps on ANY of the three axes (touched-files,
    boundary-files, consumer-symbols), NAMING the overlapping entries -- the
    disagreement IS the finding (the tool does not adjudicate which side is
    wrong). MEASURED-SAFE iff disjoint on ALL three axes.
    """
    overlap = PairOverlap(
        files=tuple(sorted(a.files & b.files)),
        boundary_files=tuple(sorted(a.boundary_files & b.boundary_files)),
        consumer_symbols=tuple(sorted(a.consumer_symbols & b.consumer_symbols)),
    )
    if overlap.is_empty:
        reasons = (
            f"measured disjoint on all three axes: {a.slice_id} and "
            f"{b.slice_id} share no touched file, no boundary file, and no "
            f"high-fan-in consumer symbol"
        )
        return PairClassification(
            ParallelSafetyVerdict.MEASURED_SAFE, overlap, (reasons,)
        )

    reasons_list: list[str] = []
    if overlap.files:
        reasons_list.append(
            f"declared parallel but measured overlap on touched files: "
            f"{', '.join(overlap.files)}"
        )
    if overlap.boundary_files:
        reasons_list.append(
            f"declared parallel but measured overlap on boundary files: "
            f"{', '.join(overlap.boundary_files)}"
        )
    if overlap.consumer_symbols:
        reasons_list.append(
            f"declared parallel but measured overlap on consumer symbols: "
            f"{', '.join(overlap.consumer_symbols)}"
        )
    return PairClassification(ParallelSafetyVerdict.DRIFT, overlap, tuple(reasons_list))
