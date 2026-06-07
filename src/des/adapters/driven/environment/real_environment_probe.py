"""RealEnvironmentProbe -- detect the host's provisionable tier.

Driven adapter for feature `walking-skeleton-production-like-gate` (DESIGN /
Component Decomposition; tier probe). Earned-Trust: probes the host before
claiming a tier, never assumes one.

  - T1 (PIP_ONLY) requires `pip` importable AND a writable temp directory.
  - T2 (DOCKER) additionally requires `docker info` to exit 0.
  - Neither -> NONE (fail-mode D).

The `docker info` probe is invoked as a subprocess, never imported -- the
adapter stays import-light.
"""

from __future__ import annotations

import importlib.util
import subprocess
import tempfile

from des.domain.tier_ladder import TierCapability
from des.ports.driven_ports.environment_probe import EnvironmentProbe


class RealEnvironmentProbe(EnvironmentProbe):
    """An `EnvironmentProbe` that probes the real host environment."""

    def detect(self) -> TierCapability:
        """Probe the host and return its highest provisionable tier."""
        if not self._pip_available() or not self._writable_temp():
            return TierCapability.NONE
        if self._docker_available():
            return TierCapability.DOCKER
        return TierCapability.PIP_ONLY

    @staticmethod
    def _pip_available() -> bool:
        """Whether `pip` is importable in the current interpreter."""
        return importlib.util.find_spec("pip") is not None

    @staticmethod
    def _writable_temp() -> bool:
        """Whether a temp file can be created and written in the temp dir."""
        try:
            with tempfile.NamedTemporaryFile() as handle:
                handle.write(b"probe")
            return True
        except OSError:
            return False

    @staticmethod
    def _docker_available() -> bool:
        """Whether `docker info` exits 0 (Docker reachable)."""
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return result.returncode == 0


__all__ = ["RealEnvironmentProbe"]
