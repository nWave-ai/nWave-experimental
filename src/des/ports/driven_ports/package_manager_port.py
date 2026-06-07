"""PackageManagerPort - driven port abstracting pipx/uv upgrade operations.

Caller resolves the absolute binary path and provides the target version.
The port MUST NOT know about PATH resolution or session lifecycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class UpgradeResult:
    """Outcome of a package upgrade attempt.

    The optional ``phase`` field identifies which sub-phase failed in the
    two-phase upgrade model (``"pm_upgrade"`` for the package-manager upgrade
    step, ``"nwave_install"`` for the post-upgrade ``nwave-ai install`` step).
    It is ``None`` on success and on legacy failures that predate phase
    tracking; callers should treat ``None`` as "phase unspecified".
    """

    success: bool
    error: str | None
    phase: str | None = None


@runtime_checkable
class PackageManagerPort(Protocol):
    """Driven port for upgrading a package to a target version."""

    def upgrade(self, pm_binary_abspath: str, target_version: str) -> UpgradeResult: ...
