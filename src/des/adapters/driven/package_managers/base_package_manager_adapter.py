"""BasePackageManagerAdapter - shared two-phase upgrade flow for pipx/uv adapters.

The pipx and uv ``PackageManagerPort`` adapters share an identical two-phase
upgrade model:

1. ``<pm> <manager-specific argv>`` - upgrade the package itself. The argv
   differs per manager (``pipx upgrade nwave-ai`` vs
   ``uv tool install nwave-ai@latest --force``); everything else is shared.
2. ``nwave-ai install`` - re-runs the nWave installer so framework assets
   (agents, skills, commands) track the newly installed package version.

This base holds the shared flow plus the 4-arm subprocess-error handling
(``TimeoutExpired`` / ``FileNotFoundError`` / ``OSError`` / non-zero
returncode). Subclasses supply ONLY the manager-specific upgrade argv and the
human-readable operation label via :meth:`_pm_upgrade_command` and
:attr:`pm_upgrade_operation` (template-method pattern).

The base is a concrete helper that adapters extend; the port stays a
``Protocol`` and is NOT inherited here. Subclasses still satisfy
``PackageManagerPort`` structurally via the inherited :meth:`upgrade`.
"""

from __future__ import annotations

import shutil
import subprocess

from des.ports.driven_ports.package_manager_port import UpgradeResult


_UPGRADE_TIMEOUT_SECONDS = 120
_PACKAGE_NAME = "nwave-ai"


class BasePackageManagerAdapter:
    """Shared two-phase ``PackageManagerPort`` flow for pipx/uv adapters."""

    #: Human-readable label for the package-manager upgrade operation, used in
    #: error messages (e.g. ``"pipx upgrade"`` or ``"uv tool install"``).
    pm_upgrade_operation: str = ""

    def _pm_upgrade_command(self, pm_binary_abspath: str) -> list[str]:
        """Build the manager-specific upgrade argv. Subclasses override."""
        raise NotImplementedError

    def upgrade(self, pm_binary_abspath: str, target_version: str) -> UpgradeResult:
        pm_result = self._run_pm_upgrade(pm_binary_abspath)
        if pm_result is not None:
            return pm_result
        return self._run_nwave_install()

    def _run_pm_upgrade(self, pm_binary_abspath: str) -> UpgradeResult | None:
        """Run the manager-specific upgrade; failure result or None on success."""
        cmd = self._pm_upgrade_command(pm_binary_abspath)
        return self._run_subprocess_phase(
            cmd,
            phase="pm_upgrade",
            operation=self.pm_upgrade_operation,
            missing_binary_path=pm_binary_abspath,
        )

    def _run_nwave_install(self) -> UpgradeResult:
        """Run the freshly upgraded ``nwave-ai install`` binary."""
        nwave_ai_path = shutil.which(_PACKAGE_NAME)
        if nwave_ai_path is None:
            return UpgradeResult(
                success=False,
                error=f"binary not found: {_PACKAGE_NAME}",
                phase="nwave_install",
            )

        cmd = [nwave_ai_path, "install"]
        failure = self._run_subprocess_phase(
            cmd,
            phase="nwave_install",
            operation="nwave-ai install",
            missing_binary_path=nwave_ai_path,
        )
        if failure is not None:
            return failure
        return UpgradeResult(success=True, error=None)

    def _run_subprocess_phase(
        self,
        cmd: list[str],
        *,
        phase: str,
        operation: str,
        missing_binary_path: str,
    ) -> UpgradeResult | None:
        """Run ``cmd`` with the shared 4-arm error handling.

        Returns a failure ``UpgradeResult`` (with ``phase`` set) on any error
        or non-zero exit, or ``None`` when the command succeeds.
        """
        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=_UPGRADE_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return UpgradeResult(
                success=False,
                error=f"timeout after {_UPGRADE_TIMEOUT_SECONDS}s running {operation}",
                phase=phase,
            )
        except FileNotFoundError:
            return UpgradeResult(
                success=False,
                error=f"binary not found: {missing_binary_path}",
                phase=phase,
            )
        except OSError as exc:
            return UpgradeResult(
                success=False,
                error=f"{operation} failed: {exc}",
                phase=phase,
            )

        if completed.returncode != 0:
            return UpgradeResult(
                success=False,
                error=completed.stderr or completed.stdout or f"{operation} failed",
                phase=phase,
            )
        return None
