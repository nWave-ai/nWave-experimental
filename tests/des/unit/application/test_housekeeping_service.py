"""
Unit tests for HousekeepingService orchestration shell and signal file cleanup.

Tests enter through the driving port: HousekeepingService.run_housekeeping().
Task stubs (_clean_audit_logs, _clean_signal_files, _rotate_skill_log) are
patched at the class boundary to verify orchestration behavior.

Orchestration Test Budget: 4 distinct behaviors x 2 = 8 max. Actual: 4 tests.
Signal File Test Budget: 5 distinct behaviors x 2 = 10 max. Actual: 5 tests.

Orchestration Behaviors:
  1. Disabled config -> no tasks run
  2. Missing nwave_dir -> returns immediately
  3. Task exception -> other tasks still run (fail-isolation)
  4. No console output under any condition

Signal File Behaviors:
  1. Stale signal file (des-task-active*) removed when older than threshold
  2. Recent signal file preserved (concurrent session safety)
  3. Stale deliver-session.json removed
  4. Missing des/ directory does not cause errors
  5. Custom staleness threshold respected
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from unittest.mock import patch


if TYPE_CHECKING:
    from pathlib import Path


class FixedTimeProvider:
    """Minimal TimeProvider stub for unit tests."""

    def __init__(self, fixed_time: datetime) -> None:
        self._fixed_time = fixed_time

    def now_utc(self) -> datetime:
        return self._fixed_time


_NOW = datetime(2026, 2, 26, 10, 0, 0, tzinfo=timezone.utc)


class TestHousekeepingServiceOrchestration:
    """HousekeepingService.run_housekeeping() orchestrates three independent tasks."""

    def test_disabled_config_skips_all_tasks(self, tmp_path: Path) -> None:
        """Given enabled=False, no files are modified or deleted."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        nwave_dir.mkdir()
        des_dir = nwave_dir / "des"
        des_dir.mkdir()

        # Create candidate files that would be cleaned if housekeeping ran
        old_signal = des_dir / "des-task-active-stale"
        old_signal.write_text("{}", encoding="utf-8")
        skill_log = nwave_dir / "skill-loading-log.jsonl"
        skill_log.write_text('{"entry": 0}\n', encoding="utf-8")

        config = HousekeepingConfig(nwave_dir=nwave_dir, enabled=False)
        HousekeepingService.run_housekeeping(config, FixedTimeProvider(_NOW))

        # Observable: no files were touched when housekeeping is disabled
        assert old_signal.exists(), "Signal file must not be removed when disabled"
        assert skill_log.exists(), "Skill log must not be modified when disabled"

    def test_missing_nwave_dir_skips_all_tasks(self, tmp_path: Path) -> None:
        """Given nwave_dir does not exist, no files are created or modified."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        # Intentionally not created
        config = HousekeepingConfig(nwave_dir=nwave_dir)
        HousekeepingService.run_housekeeping(config, FixedTimeProvider(_NOW))

        # Observable: .nwave/ was not created (no state created where none existed)
        assert not nwave_dir.exists(), (
            "No directory must be created when nwave_dir is absent"
        )

    def test_task_exception_does_not_prevent_other_tasks(self, tmp_path: Path) -> None:
        """Given _clean_audit_logs raises, _clean_signal_files and _rotate_skill_log still run."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        nwave_dir.mkdir()
        config = HousekeepingConfig(nwave_dir=nwave_dir)
        time_provider = FixedTimeProvider(_NOW)

        with (
            patch.object(
                HousekeepingService,
                "_clean_audit_logs",
                side_effect=PermissionError("simulated failure"),
            ),
            patch.object(HousekeepingService, "_clean_signal_files") as mock_signal,
            patch.object(HousekeepingService, "_rotate_skill_log") as mock_skill,
        ):
            # Must not raise despite _clean_audit_logs raising
            HousekeepingService.run_housekeeping(config, time_provider)

        mock_signal.assert_called_once()
        mock_skill.assert_called_once()

    def test_no_console_output_when_disabled(self, tmp_path: Path, capsys) -> None:
        """Given enabled=False, run_housekeeping produces no stdout/stderr output."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        config = HousekeepingConfig(nwave_dir=nwave_dir, enabled=False)
        time_provider = FixedTimeProvider(_NOW)

        HousekeepingService.run_housekeeping(config, time_provider)

        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""


class TestCleanSignalFiles:
    """HousekeepingService._clean_signal_files() removes stale signal files."""

    def _make_signal_file(
        self, des_dir: Path, name: str, age_hours: float, now: datetime
    ) -> Path:
        """Create a signal file with a controlled mtime."""
        des_dir.mkdir(parents=True, exist_ok=True)
        signal_file = des_dir / name
        signal_file.write_text("{}", encoding="utf-8")
        mtime = (now - timedelta(hours=age_hours)).timestamp()
        os.utime(signal_file, (mtime, mtime))
        return signal_file

    def test_stale_signal_file_is_removed(self, tmp_path: Path) -> None:
        """Given des-task-active* file older than threshold, it is removed."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        des_dir = nwave_dir / "des"
        now = _NOW
        self._make_signal_file(des_dir, "des-task-active-proj--step-1", 18, now)

        config = HousekeepingConfig(nwave_dir=nwave_dir)
        HousekeepingService.run_housekeeping(config, FixedTimeProvider(now))

        assert not (des_dir / "des-task-active-proj--step-1").exists()

    def test_recent_signal_file_is_preserved(self, tmp_path: Path) -> None:
        """Given des-task-active* file younger than threshold, it is preserved."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        des_dir = nwave_dir / "des"
        now = _NOW
        self._make_signal_file(des_dir, "des-task-active-proj--step-1", 0.75, now)

        config = HousekeepingConfig(nwave_dir=nwave_dir)
        HousekeepingService.run_housekeeping(config, FixedTimeProvider(now))

        assert (des_dir / "des-task-active-proj--step-1").exists()

    def test_stale_deliver_session_json_is_removed(self, tmp_path: Path) -> None:
        """Given deliver-session.json older than threshold, it is removed."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        des_dir = nwave_dir / "des"
        now = _NOW
        self._make_signal_file(des_dir, "deliver-session.json", 26, now)

        config = HousekeepingConfig(nwave_dir=nwave_dir)
        HousekeepingService.run_housekeeping(config, FixedTimeProvider(now))

        assert not (des_dir / "deliver-session.json").exists()

    def test_missing_des_dir_does_not_raise(self, tmp_path: Path) -> None:
        """Given .nwave/des/ does not exist, housekeeping completes without error."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        nwave_dir.mkdir()
        # des/ intentionally absent

        config = HousekeepingConfig(nwave_dir=nwave_dir)
        # Must not raise
        HousekeepingService.run_housekeeping(config, FixedTimeProvider(_NOW))

    def test_custom_threshold_preserves_file_below_limit(self, tmp_path: Path) -> None:
        """Given signal_staleness_hours=8 and file 5h old, file is preserved."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        des_dir = nwave_dir / "des"
        now = _NOW
        self._make_signal_file(des_dir, "des-task-active-feat--step-1", 5, now)

        config = HousekeepingConfig(nwave_dir=nwave_dir, signal_staleness_hours=8)
        HousekeepingService.run_housekeeping(config, FixedTimeProvider(now))

        assert (des_dir / "des-task-active-feat--step-1").exists()


class TestCleanAuditLogs:
    """HousekeepingService._clean_audit_logs() removes logs older than the retention cutoff.

    Tests enter through driving port: HousekeepingService.run_housekeeping().
    Signal file and skill log stubs are patched to isolate audit log behavior.

    Test Budget: 4 distinct behaviors x 2 = 8 max. Actual: 4 tests.

    Behaviors:
      1. Files strictly before cutoff deleted; files at/after cutoff preserved
      2. Today's log preserved regardless of retention setting (retention=0 edge case)
      3. Missing audit log directory does not raise
      4. PermissionError on individual file is silently skipped
    """

    def _make_log(self, logs_dir: Path, date_str: str) -> Path:
        """Create an audit log file with standard naming."""
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = logs_dir / f"audit-{date_str}.log"
        log_file.write_text("{}", encoding="utf-8")
        return log_file

    def test_deletes_files_before_cutoff_and_preserves_files_at_or_after(
        self, tmp_path: Path
    ) -> None:
        """Given retention=7 and today=2026-02-26,
        file 8 days old (2026-02-18) is deleted; file at cutoff (2026-02-19) is kept."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        nwave_dir.mkdir()
        logs_dir = nwave_dir / "des" / "logs"

        # 8 days old — strictly before cutoff → deleted
        old_log = self._make_log(logs_dir, "2026-02-18")
        # 7 days old — exactly at cutoff → preserved
        boundary_log = self._make_log(logs_dir, "2026-02-19")
        # 6 days old — after cutoff → preserved
        recent_log = self._make_log(logs_dir, "2026-02-20")

        config = HousekeepingConfig(
            nwave_dir=nwave_dir, audit_log_dir=logs_dir, audit_retention_days=7
        )

        with (
            patch.object(HousekeepingService, "_clean_signal_files"),
            patch.object(HousekeepingService, "_rotate_skill_log"),
        ):
            HousekeepingService.run_housekeeping(config, FixedTimeProvider(_NOW))

        assert not old_log.exists(), "File 8 days old must be deleted"
        assert boundary_log.exists(), (
            "File exactly at cutoff (7 days) must be preserved"
        )
        assert recent_log.exists(), "File 6 days old must be preserved"

    def test_todays_log_preserved_when_retention_is_zero(self, tmp_path: Path) -> None:
        """Given retention=0, today's log is never deleted."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        nwave_dir.mkdir()
        logs_dir = nwave_dir / "des" / "logs"
        today_log = self._make_log(logs_dir, "2026-02-26")

        config = HousekeepingConfig(
            nwave_dir=nwave_dir, audit_log_dir=logs_dir, audit_retention_days=0
        )

        with (
            patch.object(HousekeepingService, "_clean_signal_files"),
            patch.object(HousekeepingService, "_rotate_skill_log"),
        ):
            HousekeepingService.run_housekeeping(config, FixedTimeProvider(_NOW))

        assert today_log.exists(), "Today's log must never be deleted"

    def test_missing_audit_directory_does_not_raise(self, tmp_path: Path) -> None:
        """Given audit_log_dir does not exist, run_housekeeping completes without error."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        nwave_dir.mkdir()
        absent_logs_dir = tmp_path / "nonexistent" / "logs"

        config = HousekeepingConfig(nwave_dir=nwave_dir, audit_log_dir=absent_logs_dir)

        with (
            patch.object(HousekeepingService, "_clean_signal_files"),
            patch.object(HousekeepingService, "_rotate_skill_log"),
        ):
            # Must not raise
            HousekeepingService.run_housekeeping(config, FixedTimeProvider(_NOW))

        assert not absent_logs_dir.exists(), "No directory must be created"

    def test_permission_error_on_file_is_skipped(self, tmp_path: Path) -> None:
        """Given unlink raises OSError on one file, it is skipped; others are deleted.

        Note: On Linux, file read-only permissions do not prevent unlink (directory
        write permission is what matters). We simulate OSError via mock to test the
        error-handling path in a platform-independent manner.
        """
        from pathlib import Path as _Path

        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        nwave_dir.mkdir()
        logs_dir = nwave_dir / "des" / "logs"

        # Both 10 days old (before cutoff of 2026-02-19)
        deletable = self._make_log(logs_dir, "2026-02-16")
        protected = self._make_log(logs_dir, "2026-02-15")

        # Track which unlink calls fail vs succeed
        original_unlink = _Path.unlink

        def selective_unlink(self_path: _Path, missing_ok: bool = False) -> None:
            if self_path.name == protected.name:
                raise PermissionError(f"[Errno 13] Permission denied: '{self_path}'")
            original_unlink(self_path, missing_ok)

        config = HousekeepingConfig(nwave_dir=nwave_dir, audit_log_dir=logs_dir)

        with (
            patch.object(HousekeepingService, "_clean_signal_files"),
            patch.object(HousekeepingService, "_rotate_skill_log"),
            patch.object(_Path, "unlink", selective_unlink),
        ):
            # Must not raise despite permission error
            HousekeepingService.run_housekeeping(config, FixedTimeProvider(_NOW))

        assert not deletable.exists(), "Deletable old log must be removed"
        assert protected.exists(), "File with OSError on unlink must be preserved"


class TestRotateSkillLog:
    """HousekeepingService._rotate_skill_log() truncates oversized skill logs.

    Tests enter through driving port: HousekeepingService.run_housekeeping().
    Audit log and signal file stubs are patched to isolate skill log behavior.

    Test Budget: 5 distinct behaviors x 2 = 10 max. Actual: 5 tests.

    Behaviors:
      1. File below threshold -> not modified
      2. File above threshold -> truncated to last 1000 lines
      3. Most recent 1000 entries preserved after truncation
      4. Missing file -> no error, no file created
      5. Write failure (OSError) -> silently skipped, no exception propagated
    """

    def _make_skill_log(self, nwave_dir, num_lines):
        """Create a skill-loading-log.jsonl with numbered entries."""
        nwave_dir.mkdir(parents=True, exist_ok=True)
        log_file = nwave_dir / "skill-loading-log.jsonl"
        lines = [f'{{"entry": {i}}}\n' for i in range(num_lines)]
        log_file.write_text("".join(lines), encoding="utf-8")
        return log_file

    def test_file_below_threshold_is_not_modified(self, tmp_path):
        """Given log file is smaller than skill_log_max_bytes, it is not modified."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        log_file = self._make_skill_log(nwave_dir, 100)
        original_content = log_file.read_text(encoding="utf-8")

        config = HousekeepingConfig(nwave_dir=nwave_dir, skill_log_max_bytes=1_048_576)
        with (
            patch.object(HousekeepingService, "_clean_audit_logs"),
            patch.object(HousekeepingService, "_clean_signal_files"),
        ):
            HousekeepingService.run_housekeeping(config, FixedTimeProvider(_NOW))

        assert log_file.read_text(encoding="utf-8") == original_content

    def test_oversized_file_is_truncated_to_1000_lines(self, tmp_path):
        """Given log file exceeds threshold, it is truncated to exactly 1000 lines."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        log_file = self._make_skill_log(nwave_dir, 5000)
        # Force threshold below file size by setting it to 1 byte
        config = HousekeepingConfig(nwave_dir=nwave_dir, skill_log_max_bytes=1)
        with (
            patch.object(HousekeepingService, "_clean_audit_logs"),
            patch.object(HousekeepingService, "_clean_signal_files"),
        ):
            HousekeepingService.run_housekeeping(config, FixedTimeProvider(_NOW))

        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1000

    def test_most_recent_entries_preserved_after_truncation(self, tmp_path):
        """Given 5000-line log truncated, the last 1000 entries (4000-4999) are kept."""
        import json

        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        log_file = self._make_skill_log(nwave_dir, 5000)
        config = HousekeepingConfig(nwave_dir=nwave_dir, skill_log_max_bytes=1)
        with (
            patch.object(HousekeepingService, "_clean_audit_logs"),
            patch.object(HousekeepingService, "_clean_signal_files"),
        ):
            HousekeepingService.run_housekeeping(config, FixedTimeProvider(_NOW))

        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        first = json.loads(lines[0])
        last = json.loads(lines[-1])
        assert first["entry"] == 4000  # 5000 - 1000
        assert last["entry"] == 4999

    def test_missing_log_file_does_not_raise(self, tmp_path):
        """Given skill-loading-log.jsonl does not exist, run_housekeeping returns silently."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        nwave_dir.mkdir()
        skill_log = nwave_dir / "skill-loading-log.jsonl"

        config = HousekeepingConfig(nwave_dir=nwave_dir, skill_log_max_bytes=1)
        # Must not raise
        with (
            patch.object(HousekeepingService, "_clean_audit_logs"),
            patch.object(HousekeepingService, "_clean_signal_files"),
        ):
            HousekeepingService.run_housekeeping(config, FixedTimeProvider(_NOW))

        # No file should be created
        assert not skill_log.exists()

    def test_write_failure_is_silently_skipped(self, tmp_path):
        """Given log exceeds threshold but write fails, no exception propagates."""
        import stat

        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        log_file = self._make_skill_log(nwave_dir, 5000)
        # Make file read-only to trigger OSError on write
        log_file.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

        config = HousekeepingConfig(nwave_dir=nwave_dir, skill_log_max_bytes=1)
        try:
            # Must not raise
            with (
                patch.object(HousekeepingService, "_clean_audit_logs"),
                patch.object(HousekeepingService, "_clean_signal_files"),
            ):
                HousekeepingService.run_housekeeping(config, FixedTimeProvider(_NOW))
        finally:
            # Restore permissions for cleanup
            log_file.chmod(stat.S_IRWXU)
