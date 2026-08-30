"""Driven port for host-specific worktree residence durability."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path

    from des.domain.worktree_residence import ResidenceDurability
    from des.ports.driven_ports.committed_scope_port import Indeterminate


class ResidenceDurabilityPort(ABC):
    @abstractmethod
    def classify(self, root: Path) -> ResidenceDurability:
        """Return a total, fail-closed durability classification."""
        ...

    @abstractmethod
    def durable_default(self, repo: Path) -> Path | None:
        """Derive a repository-bound default; never return a path literal."""
        ...

    @abstractmethod
    def freeze(self, root: Path) -> bool | Indeterminate:
        """Prevent further nWave mutation, or report that it cannot be proven."""
        ...


__all__ = ["ResidenceDurabilityPort"]
