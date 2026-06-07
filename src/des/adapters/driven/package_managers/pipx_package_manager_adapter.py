"""PipxPackageManagerAdapter - real pipx-backed PackageManagerPort implementation.

Two-phase upgrade model (shared flow lives in
:class:`BasePackageManagerAdapter`):

1. ``<pipx> upgrade nwave-ai`` - delegates version selection to pipx (it
   always upgrades to the latest version satisfying any existing pins).
2. ``nwave-ai install`` - re-runs the nWave installer so framework assets
   (agents, skills, commands) track the newly installed package version.

This adapter supplies ONLY the pipx-specific upgrade argv and operation label;
the shared flow and the 4-arm subprocess-error handling are inherited.

Failures are reported via ``UpgradeResult.phase`` as ``"pm_upgrade"`` or
``"nwave_install"`` so the caller can tailor remediation.
"""

from __future__ import annotations

# ``subprocess`` and ``shutil`` are re-exported at this module's namespace so
# unit tests patching ``...pipx_package_manager_adapter.subprocess.run`` /
# ``...shutil.which`` can resolve the module attribute. They bind the same
# singleton module objects the base flow uses, so patching either module path
# transparently affects the inherited two-phase upgrade.
import shutil
import subprocess

from des.adapters.driven.package_managers.base_package_manager_adapter import (
    _PACKAGE_NAME,
    BasePackageManagerAdapter,
)


__all__ = ["PipxPackageManagerAdapter", "shutil", "subprocess"]


class PipxPackageManagerAdapter(BasePackageManagerAdapter):
    """PackageManagerPort adapter that shells out to pipx."""

    pm_upgrade_operation = "pipx upgrade"

    def _pm_upgrade_command(self, pm_binary_abspath: str) -> list[str]:
        return [pm_binary_abspath, "upgrade", _PACKAGE_NAME]
