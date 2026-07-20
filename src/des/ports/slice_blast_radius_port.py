"""`SliceBlastRadiusPort` -- the driven, READ-ONLY measurement seam.

Feature-delta: docs/feature/measured-parallel-safety-report/feature-delta.md
  ([REF] Driven Ports + Adapters, Effect Isolation).

The report core measures a declared-parallel slice's scope through THIS port,
never by shelling `des blast-radius` directly -- the subprocess/git indirection
is owned entirely by the adapter (D-6). The port is READ-ONLY: it exposes only
`measure(...)` and no write method (Effect Isolation -- a driving/driven port
that only reads must not expose a write surface).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from des.domain.parallel_safety import SliceMeasurement, SliceUnmeasured


@dataclass(frozen=True)
class SliceScope:
    """The explicit repo-relative path-set bound to a declared-parallel slice.

    The measurable input forwarded verbatim to `des blast-radius --paths`
    (DB) -- the report does not resolve slice->git-range itself (that would be
    new git logic in the report layer, violating D-6).
    """

    paths: tuple[str, ...]


class SliceBlastRadiusPort(ABC):
    """Read-only measurement seam: measure one slice's scope's blast radius."""

    @abstractmethod
    def measure(
        self, slice_id: str, scope: SliceScope, timeout_s: float
    ) -> SliceMeasurement | SliceUnmeasured:
        """Measure `scope`'s blast radius for `slice_id`.

        Returns a `SliceMeasurement` when the measurement was taken, or a
        `SliceUnmeasured` (D-4) when it could not be -- e.g. a `des blast-radius`
        timeout on a high-fan-in file. Never coerces an unmeasured result into a
        fabricated measurement.
        """
        raise NotImplementedError
