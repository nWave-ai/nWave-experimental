"""NullPackageManager - no-op adapter used when the package manager is unknown.

This adapter satisfies the ``PackageManagerPort`` contract so callers never
need to deal with ``None``. In practice ``PendingUpdateService`` exits via the
``flag.pm == "unknown"`` branch before invoking ``upgrade()``, so this adapter's
``upgrade()`` acts as a defensive fallback that reports a structured failure
rather than raising.
"""

from __future__ import annotations

from des.ports.driven_ports.package_manager_port import UpgradeResult


class NullPackageManager:
    """No-op ``PackageManagerPort`` implementation for ``pm == "unknown"``."""

    def upgrade(self, pm_binary_abspath: str, target_version: str) -> UpgradeResult:
        return UpgradeResult(
            success=False,
            error="no-op: package manager unknown",
            phase="pm_upgrade",
        )
