"""Driven port for the positive owner-lease assertion."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path

    from des.domain.worktree_residence import LaneIdentity, OwnerLease


class OwnerLeaseProbe(ABC):
    @abstractmethod
    def observe(
        self, worktree_root: Path, expected_identity: LaneIdentity
    ) -> OwnerLease:
        """Read HELD/RELEASED, or INDETERMINATE when no trustworthy fact exists."""
        ...


__all__ = ["OwnerLeaseProbe"]
