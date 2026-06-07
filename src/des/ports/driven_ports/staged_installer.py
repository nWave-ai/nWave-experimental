"""StagedInstaller -- driven port: install the artifact into a clean prefix.

Feature `walking-skeleton-production-like-gate` (DESIGN / Staged-Install
Fixture, step 3). Installs the built artifact into a fresh, isolated prefix
so the walking-skeleton AT exercises the *installed* artifact, never `src/`.

Defined by: `WalkingSkeletonGate` requirements.
Implemented by: `PipTargetInstaller` (`pip install --target`).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


class StagedInstallError(Exception):
    """Raised when staging the artifact into a clean prefix fails (RM-6)."""


@dataclass(frozen=True)
class InstalledTree:
    """The installed artifact -- the staged prefix the AT runs against.

    `prefix` is the directory the artifact was installed into; `python_path`
    is the value to put on `PYTHONPATH` so the AT subprocess imports the
    installed modules, not `src/`.
    """

    prefix: Path
    python_path: Path


class StagedInstaller(ABC):
    """Driven port: install a built artifact into a clean staged prefix."""

    @abstractmethod
    def install(self, artifact: Path, prefix: Path) -> InstalledTree:
        """Install `artifact` into `prefix`; return the `InstalledTree`.

        Raises `StagedInstallError` on an install failure.
        """
        raise NotImplementedError


__all__ = ["InstalledTree", "StagedInstallError", "StagedInstaller"]
