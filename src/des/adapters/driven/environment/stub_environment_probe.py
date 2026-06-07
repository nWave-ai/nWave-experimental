"""StubEnvironmentProbe -- a deterministic `EnvironmentProbe` for tests.

Driven adapter for feature `walking-skeleton-production-like-gate` (DESIGN /
Component Decomposition; tier probe). Reports a pre-configured
`TierCapability` so acceptance tests can drive the gate's tier behaviour
without depending on the host's actual Docker availability.

The project Infrastructure Policy fakes only the non-deterministic
`EnvironmentProbe`; the build + install remain real (`BuildDistArtifactBuilder`
+ `PipTargetInstaller`).
"""

from __future__ import annotations

from des.domain.tier_ladder import TierCapability
from des.ports.driven_ports.environment_probe import EnvironmentProbe


class StubEnvironmentProbe(EnvironmentProbe):
    """An `EnvironmentProbe` that reports a fixed, injected tier capability."""

    def __init__(self, capability: TierCapability = TierCapability.PIP_ONLY) -> None:
        self._capability = capability

    def detect(self) -> TierCapability:
        """Return the injected tier capability."""
        return self._capability


__all__ = ["StubEnvironmentProbe"]
