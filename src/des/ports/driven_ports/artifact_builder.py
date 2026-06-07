"""ArtifactBuilder -- driven port: build the delivered artifact.

Feature `walking-skeleton-production-like-gate` (DESIGN / Staged-Install
Fixture, step 1). Builds the artifact a consumer installs -- the `.whl` or
staged tree -- from a feature's source root.

Defined by: `WalkingSkeletonGate` requirements.
Implemented by: `BuildDistArtifactBuilder` (wraps the feature's build via
subprocess).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


class ArtifactBuildError(Exception):
    """Raised when the artifact build fails (DESIGN RM-6 -- `build-failed`)."""


class ArtifactBuilder(ABC):
    """Driven port: build a feature's delivered artifact from its source."""

    @abstractmethod
    def build(self, feature_root: Path) -> Path:
        """Build the delivered artifact and return the path to it.

        Raises `ArtifactBuildError` on a build failure -- the gate maps this
        to fail-mode D with `reason=build-failed`.
        """
        raise NotImplementedError


__all__ = ["ArtifactBuildError", "ArtifactBuilder"]
