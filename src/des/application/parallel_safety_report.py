"""`run_parallel_safety_report` -- the READ-ONLY report orchestrator.

Feature-delta: docs/feature/measured-parallel-safety-report/feature-delta.md
  ([REF] Component Decomposition, [REF] Driving Ports -- Effect Isolation).

Orchestrates: receive the declared-parallel pair (ids + scopes as data) ->
`port.measure` each -> short-circuit to UNMEASURED if either could not be
measured (D-4) -> else `classify_pair`. No git, no I/O beyond the port
(plan-value pattern): returns a `ParallelSafetyReport` value and mutates
nothing; the CLI shell is the only thing that writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.domain.parallel_safety import (
    PairOverlap,
    ParallelSafetyVerdict,
    SliceMeasurement,
    SliceUnmeasured,
    classify_pair,
)


if TYPE_CHECKING:
    from des.ports.slice_blast_radius_port import SliceBlastRadiusPort, SliceScope


#: The verdict token surface (mirrors the domain enum values + the
#: unmeasured token, which lives only here -- never in `classify_pair`'s
#: codomain, D-4/DG).
UNMEASURED = "UNMEASURED"


@dataclass(frozen=True)
class ParallelSafetyReport:
    """The advisory report for ONE declared-parallel pair.

    `verdict` is a closed token ({MEASURED-SAFE, DRIFT, UNMEASURED}). `overlap`
    names the measured overlap (empty on MEASURED-SAFE). `unmeasured` is set
    ONLY on the UNMEASURED verdict (D-4), naming the slice + scope that could
    not be measured. Read-only value -- no side effects.
    """

    verdict: str
    pair: tuple[str, str]
    overlap: PairOverlap
    reasons: tuple[str, ...]
    unmeasured: SliceUnmeasured | None = None


def run_parallel_safety_report(
    port: SliceBlastRadiusPort,
    pair: tuple[tuple[str, SliceScope], tuple[str, SliceScope]],
    timeout_s: float,
) -> ParallelSafetyReport:
    """Measure both declared-parallel slices and classify the pair. Read-only.

    Short-circuits to UNMEASURED (naming the offending slice + its scope
    paths) if EITHER measurement could not be taken -- never coerced to a
    safe/unsafe verdict (D-4). Otherwise delegates the disjointness decision to
    the pure `classify_pair`.
    """
    (id_a, scope_a), (id_b, scope_b) = pair
    measured_a = port.measure(id_a, scope_a, timeout_s)
    measured_b = port.measure(id_b, scope_b, timeout_s)

    pair_ids = (id_a, id_b)
    for measured in (measured_a, measured_b):
        if isinstance(measured, SliceUnmeasured):
            return ParallelSafetyReport(
                verdict=UNMEASURED,
                pair=pair_ids,
                overlap=PairOverlap(),
                reasons=(measured.reason,),
                unmeasured=measured,
            )

    assert isinstance(measured_a, SliceMeasurement)
    assert isinstance(measured_b, SliceMeasurement)
    classification = classify_pair(measured_a, measured_b)
    return ParallelSafetyReport(
        verdict=_verdict_token(classification.verdict),
        pair=pair_ids,
        overlap=classification.overlap,
        reasons=classification.reasons,
    )


def _verdict_token(verdict: ParallelSafetyVerdict) -> str:
    """The wire token for a classifier verdict (the enum value)."""
    return verdict.value
