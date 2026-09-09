"""`InMemoryBlastRadiusAdapter` -- the in-process `SliceBlastRadiusPort` twin.

Feature-delta: docs/feature/measured-parallel-safety-report/feature-delta.md
  ([REF] Driven Ports + Adapters).

Returns canned `SliceMeasurement` / `SliceUnmeasured` keyed by slice-id, so
tests drive MEASURED-SAFE / DRIFT / UNMEASURED deterministically without a real
git repo or a `des blast-radius` fork. No subprocess, no git -- the fake
counterpart of the real subprocess adapter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from des.ports.slice_blast_radius_port import SliceBlastRadiusPort


if TYPE_CHECKING:
    from collections.abc import Mapping

    from des.domain.parallel_safety import SliceMeasurement, SliceUnmeasured
    from des.ports.slice_blast_radius_port import SliceScope


class InMemoryBlastRadiusAdapter(SliceBlastRadiusPort):
    """Serves pre-seeded results keyed by slice-id."""

    def __init__(
        self, results: Mapping[str, SliceMeasurement | SliceUnmeasured]
    ) -> None:
        self._results = dict(results)

    def measure(
        self, slice_id: str, scope: SliceScope, timeout_s: float
    ) -> SliceMeasurement | SliceUnmeasured:
        if slice_id not in self._results:
            raise KeyError(
                f"InMemoryBlastRadiusAdapter has no canned result for "
                f"{slice_id!r}; seeded: {sorted(self._results)}"
            )
        return self._results[slice_id]
