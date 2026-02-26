"""
Housekeeping Service — Application Layer.

Manages DES housekeeping operations: audit log retention, signal file staleness
cleanup, and skill log rotation. This module defines the HousekeepingConfig
value object and HousekeepingService application service used across housekeeping
operations.

Task stubs are implemented progressively:
- _clean_audit_logs: step 02-01
- _clean_signal_files: step 02-02
- _rotate_skill_log: step 02-03
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from des.ports.driven_ports.time_provider_port import TimeProvider


@dataclasses.dataclass(frozen=True)
class HousekeepingConfig:
    """
    Configuration value object for DES housekeeping operations.

    Immutable (frozen dataclass). All fields have safe defaults so it can
    be constructed with zero arguments.

    Attributes:
        enabled: Whether housekeeping is active. Default: True.
        audit_retention_days: How many days of audit logs to retain. Default: 7.
        signal_staleness_hours: Hours before a signal file is considered stale. Default: 4.
        skill_log_max_bytes: Maximum size of skill-loading log before rotation. Default: 1 MiB.
        nwave_dir: Root .nwave directory for the project. Default: cwd / ".nwave".
        audit_log_dir: Override for audit log directory. None = use AuditLogPathResolver.
    """

    enabled: bool = True
    audit_retention_days: int = 7
    signal_staleness_hours: int = 4
    skill_log_max_bytes: int = 1_048_576
    nwave_dir: Path = dataclasses.field(default_factory=lambda: Path.cwd() / ".nwave")
    audit_log_dir: Path | None = None


class HousekeepingService:
    """Application service that orchestrates DES housekeeping operations.

    All tasks run independently with per-task fail-isolation. A failure in
    one task never prevents other tasks from running, and no exception ever
    propagates to the caller.
    """

    @staticmethod
    def run_housekeeping(
        config: HousekeepingConfig,
        time_provider: TimeProvider,
    ) -> None:
        """Run all housekeeping tasks with fail-open semantics.

        Args:
            config: Housekeeping configuration value object.
            time_provider: Provides the current UTC time for age calculations.
        """
        if not config.enabled:
            return
        if not config.nwave_dir.exists():
            return
        try:
            HousekeepingService._clean_audit_logs(config, time_provider)
        except Exception:
            pass
        try:
            HousekeepingService._clean_signal_files(config, time_provider)
        except Exception:
            pass
        try:
            HousekeepingService._rotate_skill_log(config)
        except Exception:
            pass

    @staticmethod
    def _clean_audit_logs(
        config: HousekeepingConfig,
        time_provider: TimeProvider,
    ) -> None:
        """Remove audit log files beyond the retention period.

        Stub — implemented in step 02-01.
        """
        pass

    @staticmethod
    def _clean_signal_files(
        config: HousekeepingConfig,
        time_provider: TimeProvider,
    ) -> None:
        """Remove stale signal files left by crashed sessions.

        Stub — implemented in step 02-02.
        """
        pass

    @staticmethod
    def _rotate_skill_log(config: HousekeepingConfig) -> None:
        """Truncate oversized skill tracking log to the most recent entries.

        Stub — implemented in step 02-03.
        """
        pass
