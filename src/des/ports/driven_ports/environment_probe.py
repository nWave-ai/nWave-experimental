"""EnvironmentProbe -- driven port: detect the host's provisionable tier.

Feature `walking-skeleton-production-like-gate` (DESIGN / Component
Decomposition). Earned-Trust mandatory: the gate probes the environment
before claiming a tier, never assumes one (DESIGN tier probe).

Defined by: `WalkingSkeletonGate` requirements.
Implemented by: `RealEnvironmentProbe` (production), `StubEnvironmentProbe`
(tests).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from des.domain.tier_ladder import TierCapability


class EnvironmentProbe(ABC):
    """Driven port: report what fidelity tier the host can provision."""

    @abstractmethod
    def detect(self) -> TierCapability:
        """Return the highest tier capability the host can provision."""
        raise NotImplementedError


__all__ = ["EnvironmentProbe"]
