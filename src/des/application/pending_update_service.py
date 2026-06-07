"""PendingUpdateService - application service for deferred nWave self-update.

Driving port for the deferred update workflow:

- ``request_update()`` is invoked by the ``/nw-update`` slash command to persist
  a :class:`PendingUpdateFlag` that will be replayed on the next session start.
- ``apply()`` is invoked by the SessionStart early-phase handler. It reads the
  flag (no-op if absent), calls the configured :class:`PackageManagerPort` with
  the stored binary path + target version, clears the flag on success, and
  returns the :class:`UpgradeResult`.

This step is a minimal stub: attempt-cap / failure accounting is deferred to
roadmap step 03-01. On failure the flag is preserved so a later retry can
surface it.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, TYPE_CHECKING, Literal

from des.domain.pending_update_flag import PendingUpdateFlag
from des.ports.driven_ports.package_manager_port import UpgradeResult


_MANUAL_INTERVENTION_MESSAGE = (
    "attempt cap reached: please re-run the update command manually"
)
_UNKNOWN_PM_MESSAGE = "unknown package manager"
_ATTEMPT_CAP = 3


if TYPE_CHECKING:
    from des.adapters.driven.config.des_config import DESConfig
    from des.ports.driven_ports.package_manager_port import PackageManagerPort


class PendingUpdateService:
    """Driving port for deferred nWave self-updates."""

    def __init__(
        self,
        config: DESConfig,
        pm: PackageManagerPort,
        current_version: str = "unknown",
        stderr: IO[str] | None = None,
    ) -> None:
        self._config = config
        self._pm = pm
        self._current_version = current_version
        self._stderr = stderr if stderr is not None else sys.stderr

    def request_update(
        self,
        pm: Literal["pipx", "uv", "unknown"],
        pm_binary_abspath: str,
        target_version: str,
    ) -> None:
        """Persist a PendingUpdateFlag for replay at next session start."""
        flag = PendingUpdateFlag(
            pm=pm,
            pm_binary_abspath=pm_binary_abspath,
            target_version=target_version,
            requested_at=datetime.now(timezone.utc).isoformat(),
        )
        self._config.save_pending_update_state(flag)

    def apply(self) -> UpgradeResult:
        """Replay a pending update, if any. No-op when no flag is present.

        Enforces the attempt cap (N=3): if the stored flag already reports the
        cap reached, drop it and return a manual-intervention result without
        invoking the package manager. On failure, increment ``attempt_count``
        and persist the updated flag so the next session can retry or cap out.
        """
        flag = self._config.read_pending_update()
        if flag is None:
            return UpgradeResult(success=True, error=None)

        if flag.pm == "unknown":
            self._emit(
                "Cannot apply update: package manager unknown. "
                "Run `nwave-ai install` manually."
            )
            updated = replace(flag, last_error=_UNKNOWN_PM_MESSAGE)
            self._config.save_pending_update_state(updated)
            return UpgradeResult(success=False, error=_UNKNOWN_PM_MESSAGE)

        if not Path(flag.pm_binary_abspath).exists():
            error = f"binary not found: {flag.pm_binary_abspath}"
            updated = replace(
                flag,
                attempt_count=flag.attempt_count + 1,
                last_error=error,
            )
            self._config.save_pending_update_state(updated)
            self._emit(
                f"nWave update failed (attempt {updated.attempt_count}/"
                f"{_ATTEMPT_CAP}): {error}. Session continuing with "
                f"{self._current_version}."
            )
            return UpgradeResult(success=False, error=error)

        if flag.attempt_cap_reached():
            self._config.clear_pending_update()
            self._emit(
                f"nWave update abandoned after {_ATTEMPT_CAP} failed attempts: "
                f"{flag.last_error}. Run `nwave-ai install` manually."
            )
            return UpgradeResult(success=False, error=_MANUAL_INTERVENTION_MESSAGE)

        self._emit(
            f"Updating nWave ({self._current_version} \u2192 "
            f"{flag.target_version})... (~30s)"
        )
        result = self._pm.upgrade(flag.pm_binary_abspath, flag.target_version)
        if result.success:
            self._config.clear_pending_update()
            self._emit("nWave updated. Session continuing.")
            return result

        persisted_error = (
            f"[{result.phase}] {result.error}"
            if result.phase is not None
            else result.error
        )
        updated = replace(
            flag,
            attempt_count=flag.attempt_count + 1,
            last_error=persisted_error,
        )
        self._config.save_pending_update_state(updated)
        self._emit(
            f"nWave update failed (attempt {updated.attempt_count}/{_ATTEMPT_CAP}): "
            f"{persisted_error}. Session continuing with {self._current_version}."
        )
        return result

    def _emit(self, message: str) -> None:
        self._stderr.write(message + "\n")
