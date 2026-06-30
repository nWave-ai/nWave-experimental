"""Feature-delta content driven port (slice-07, nwave-flow-v2-enforcement).

A read-only capability port (principle 12) the DISCUSS gate-OUT consumes. Returns
the raw feature-delta Markdown content, or ``None`` when the artefact is absent /
unreadable so the pure ``DiscussGateOut.evaluate`` core decides INDETERMINATE
(degrade-LOUD, §17 no-silent-pass).

Asymmetric authority (§22.0): the gate VETOES; it never writes the feature-delta,
so this port exposes ONLY a read.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


class FeatureDeltaReader(ABC):
    """Driven, read-only port over the feature-delta artefact."""

    @abstractmethod
    def read(self, project_root: Path, feature_id: str) -> str | None:
        """Return the feature-delta Markdown content, or ``None`` if unreadable.

        Resolves the artefact for ``feature_id`` under ``project_root`` (the
        DESIGN-PINNED ``docs/feature/{feature_id}/feature-delta.md`` location).
        Absent / unreadable artefact -> ``None`` (NOT raise -- the pure core maps
        ``None`` to INDETERMINATE, degrade-LOUD). A present, readable artefact ->
        its full text content.

        DEVIATION (justified): the DESIGN slice-07 pseudocode shows
        ``read(project_root)``; the artefact path is keyed on the feature id, so
        the deterministic resolution requires the feature id rather than a glob
        heuristic over ``docs/feature/*``. The filesystem read MECHANICS are
        explicitly crafter-owned (DESIGN "Left to crafter"); the contract shape
        (read-only capability, ``None`` on unreadable -> degrade-LOUD) is held.
        """
        ...
