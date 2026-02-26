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
import datetime
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from des.ports.driven_ports.time_provider_port import TimeProvider


# Audit log filename slicing constants (audit-YYYY-MM-DD.log)
_AUDIT_PREFIX_LEN: int = len("audit-")  # 6
_AUDIT_SUFFIX_LEN: int = len(".log")  # 4

# Number of tail lines retained after skill log rotation
_SKILL_LOG_TAIL_LINES: int = 1000


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
    def _resolve_audit_dir(config: HousekeepingConfig) -> Path:
        """Return the audit log directory path from config or path resolver."""
        if config.audit_log_dir is not None:
            return config.audit_log_dir
        from des.domain.audit_log_path_resolver import AuditLogPathResolver

        return AuditLogPathResolver(cwd=config.nwave_dir.parent).resolve()

    @staticmethod
    def _clean_audit_logs(
        config: HousekeepingConfig,
        time_provider: TimeProvider,
    ) -> None:
        """Remove audit log files beyond the retention period.

        Scans the audit log directory for files matching audit-YYYY-MM-DD.log.
        Files strictly older than the cutoff date are deleted. Today's log and
        files at or after the cutoff are always preserved.

        Cutoff is exclusive: cutoff = today - retention_days.
        Files with file_date < cutoff are deleted; file_date == cutoff is kept.
        """
        audit_dir = HousekeepingService._resolve_audit_dir(config)
        if not audit_dir.exists():
            return

        today = time_provider.now_utc().date()
        cutoff = today - datetime.timedelta(days=config.audit_retention_days)

        for log_file in audit_dir.iterdir():
            name = log_file.name
            if not (name.startswith("audit-") and name.endswith(".log")):
                continue
            date_str = name[_AUDIT_PREFIX_LEN:-_AUDIT_SUFFIX_LEN]
            try:
                file_date = datetime.date.fromisoformat(date_str)
            except ValueError:
                continue
            if file_date == today:
                continue
            if file_date < cutoff:
                try:
                    log_file.unlink()
                except OSError:
                    pass

    @staticmethod
    def _clean_signal_files(
        config: HousekeepingConfig,
        time_provider: TimeProvider,
    ) -> None:
        """Remove stale signal files left by crashed sessions.

        Scans .nwave/des/ for des-task-active* files and deliver-session.json.
        Files older than signal_staleness_hours are deleted. Recent files are
        preserved to protect concurrent active sessions.
        """
        des_dir = config.nwave_dir / "des"
        if not des_dir.exists():
            return

        now_ts = time_provider.now_utc().timestamp()
        threshold_seconds = config.signal_staleness_hours * 3600
        cutoff_ts = now_ts - threshold_seconds

        candidates: list[Path] = list(des_dir.glob("des-task-active*"))
        deliver_session = des_dir / "deliver-session.json"
        if deliver_session.exists():
            candidates.append(deliver_session)

        for signal_file in candidates:
            try:
                mtime = signal_file.stat().st_mtime
                if mtime < cutoff_ts:
                    signal_file.unlink()
            except OSError:
                pass  # skip files we can't stat or delete

    @staticmethod
    def _rotate_skill_log(config: HousekeepingConfig) -> None:
        """Truncate oversized skill tracking log to the most recent entries.

        Checks file size as a first gate. If the file is at or below
        skill_log_max_bytes, no action is taken. If over threshold, the file
        is rewritten with only the last 1000 lines (_SKILL_LOG_TAIL_LINES), preserving
        the most recent entries. Silently skips on any OSError (locked or read-only file).
        """
        skill_log = config.nwave_dir / "skill-loading-log.jsonl"
        if not skill_log.exists():
            return

        size = skill_log.stat().st_size
        if size <= config.skill_log_max_bytes:
            return  # under threshold, no action needed

        try:
            lines = skill_log.read_text(encoding="utf-8").splitlines()
            tail_lines = lines[-_SKILL_LOG_TAIL_LINES:]
            skill_log.write_text("\n".join(tail_lines) + "\n", encoding="utf-8")
        except OSError:
            pass  # silently skip if file is locked or unwritable
