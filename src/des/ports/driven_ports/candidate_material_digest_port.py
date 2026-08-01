"""Independent byte-digest observation boundary for candidate lineage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:
    from des.domain.codex_parity import CandidateLocator, MaterialDigestObservation


class CandidateMaterialDigestPort(Protocol):
    def digest(self, locator: CandidateLocator) -> MaterialDigestObservation:
        """Re-read and digest exactly the material identified by ``locator``."""
        ...


__all__ = ["CandidateMaterialDigestPort"]
