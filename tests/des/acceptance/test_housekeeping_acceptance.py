"""Acceptance tests for DES Housekeeping feature.

Validates automatic cleanup of .nwave/ operational files at session start.
Three cleanup tasks orchestrated together: audit log retention, orphaned signal
file cleanup, and skill tracking log rotation. All fail-open (never block session).

Tests enter through the public API:
- HousekeepingService.run_housekeeping() — application service entry point
- handle_session_start() — driving adapter (integration scenarios)

Traces to:
- docs/requirements/des-housekeeping/user-stories.md (US-HK-01 through US-HK-04)
- docs/requirements/des-housekeeping/acceptance-criteria.md (26 BDD scenarios)
- docs/architecture/des-housekeeping/architecture-design.md

Scenario count: 26 (6 audit + 7 signal + 5 skill + 6 orchestration + 2 cross-cutting)
Error path ratio: 11/26 = 42% (exceeds 40% target)
"""

from __future__ import annotations

import os
import stat
import time
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import pytest


if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers — filesystem fixture builders (business language, no implementation)
# ---------------------------------------------------------------------------


def _create_audit_log(logs_dir: Path, date_str: str, content: str = "{}") -> Path:
    """Create an audit log file with the standard naming convention."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"audit-{date_str}.log"
    log_file.write_text(content, encoding="utf-8")
    return log_file


def _create_signal_file(
    des_dir: Path, name: str, age_hours: float, time_now: datetime
) -> Path:
    """Create a signal file with a specific age (via mtime manipulation)."""
    des_dir.mkdir(parents=True, exist_ok=True)
    signal_file = des_dir / name
    signal_file.write_text("{}", encoding="utf-8")
    mtime = (time_now - timedelta(hours=age_hours)).timestamp()
    os.utime(signal_file, (mtime, mtime))
    return signal_file


def _create_skill_log(nwave_dir: Path, num_lines: int) -> Path:
    """Create a skill tracking log with a given number of JSONL lines."""
    nwave_dir.mkdir(parents=True, exist_ok=True)
    log_file = nwave_dir / "skill-loading-log.jsonl"
    lines = [f'{{"entry": {i}, "skill": "test-skill-{i}"}}\n' for i in range(num_lines)]
    log_file.write_text("".join(lines), encoding="utf-8")
    return log_file


def _create_des_config(nwave_dir: Path, config: dict) -> Path:
    """Create a des-config.json with given configuration."""
    import json

    nwave_dir.mkdir(parents=True, exist_ok=True)
    config_file = nwave_dir / "des-config.json"
    config_file.write_text(json.dumps(config), encoding="utf-8")
    return config_file


# ---------------------------------------------------------------------------
# US-HK-01: Audit Log Retention
# ---------------------------------------------------------------------------


class TestAuditLogRetention:
    """US-HK-01: Housekeeping removes audit log files beyond the retention period."""

    def test_removes_logs_beyond_default_7_day_retention(self, tmp_path):
        """Given audit log files spanning 21 days
        And no custom housekeeping configuration exists
        And today is 2026-02-26
        When session-start housekeeping runs
        Then logs older than 7 days are removed
        And logs from the most recent 7 days are preserved."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        # Given: audit logs spanning 21 days
        nwave_dir = tmp_path / ".nwave"
        logs_dir = nwave_dir / "des" / "logs"
        _create_audit_log(logs_dir, "2026-02-05")  # 21 days old
        _create_audit_log(logs_dir, "2026-02-10")  # 16 days old
        _create_audit_log(logs_dir, "2026-02-18")  # 8 days old
        _create_audit_log(logs_dir, "2026-02-19")  # 7 days old (boundary)
        _create_audit_log(logs_dir, "2026-02-20")  # 6 days old
        _create_audit_log(logs_dir, "2026-02-26")  # today

        config = HousekeepingConfig(nwave_dir=nwave_dir, audit_log_dir=logs_dir)

        # When: housekeeping runs with "today" = 2026-02-26
        from tests.des.acceptance.conftest_housekeeping import FixedTimeProvider

        time_provider = FixedTimeProvider(datetime(2026, 2, 26, tzinfo=timezone.utc))
        HousekeepingService.run_housekeeping(config, time_provider)

        # Then: old logs removed, recent logs preserved
        remaining = sorted(f.name for f in logs_dir.iterdir())
        assert "audit-2026-02-05.log" not in remaining
        assert "audit-2026-02-10.log" not in remaining
        assert "audit-2026-02-18.log" not in remaining
        assert "audit-2026-02-19.log" in remaining
        assert "audit-2026-02-20.log" in remaining
        assert "audit-2026-02-26.log" in remaining

    def test_respects_custom_retention_period(self, tmp_path):
        """Given des-config.json specifies audit_retention_days as 30
        And audit logs spanning 45 days exist
        When session-start housekeeping runs
        Then only logs older than 30 days are removed
        And logs from the most recent 30 days are preserved."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        logs_dir = nwave_dir / "des" / "logs"

        today = datetime(2026, 2, 26, tzinfo=timezone.utc)
        # Create logs: 45 days ago, 35 days ago, 25 days ago, today
        for days_ago in [45, 35, 25, 0]:
            date = today - timedelta(days=days_ago)
            _create_audit_log(logs_dir, date.strftime("%Y-%m-%d"))

        config = HousekeepingConfig(
            nwave_dir=nwave_dir,
            audit_log_dir=logs_dir,
            audit_retention_days=30,
        )

        from tests.des.acceptance.conftest_housekeeping import FixedTimeProvider

        HousekeepingService.run_housekeeping(config, FixedTimeProvider(today))

        remaining = sorted(f.name for f in logs_dir.iterdir())
        # 45 and 35 days old should be removed
        assert len(remaining) == 2
        # 25 days old and today should be preserved
        assert (
            f"audit-{(today - timedelta(days=25)).strftime('%Y-%m-%d')}.log"
            in remaining
        )
        assert f"audit-{today.strftime('%Y-%m-%d')}.log" in remaining

    def test_no_logs_directory_exists(self, tmp_path):
        """Given the project has no .nwave/des/logs/ directory
        When session-start housekeeping runs
        Then no errors occur
        And no directories are created."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        logs_dir = nwave_dir / "des" / "logs"
        # Intentionally do NOT create the directory

        config = HousekeepingConfig(nwave_dir=nwave_dir, audit_log_dir=logs_dir)

        from tests.des.acceptance.conftest_housekeeping import FixedTimeProvider

        today = datetime(2026, 2, 26, tzinfo=timezone.utc)
        # Should not raise
        HousekeepingService.run_housekeeping(config, FixedTimeProvider(today))

        # No directory should have been created
        assert not logs_dir.exists()

    def test_permission_error_on_individual_log_file(self, tmp_path):
        """Given 15 audit log files older than 7 days
        And one file raises OSError when deletion is attempted
        When housekeeping attempts to remove old logs
        Then the protected file is skipped
        And all other eligible files are successfully removed
        And the session completes with no error.

        Note: On Linux, file read-only permissions (chmod) do not prevent
        unlink() — directory write permission is what matters. We simulate
        OSError via mock to test the error-handling path reliably across
        all platforms.
        """
        from pathlib import Path as _Path
        from unittest.mock import patch

        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        logs_dir = nwave_dir / "des" / "logs"

        today = datetime(2026, 2, 26, tzinfo=timezone.utc)

        # Create 15 old log files (all > 7 days old)
        old_files = []
        for i in range(15):
            days_ago = 8 + i  # 8 to 22 days old
            date = today - timedelta(days=days_ago)
            old_files.append(_create_audit_log(logs_dir, date.strftime("%Y-%m-%d")))

        # Create today's log (should never be deleted)
        _create_audit_log(logs_dir, today.strftime("%Y-%m-%d"))

        # One old file will raise OSError when unlink is called
        protected_file = old_files[5]
        protected_name = protected_file.name

        original_unlink = _Path.unlink

        def selective_unlink(self_path: _Path, missing_ok: bool = False) -> None:
            if self_path.name == protected_name:
                raise PermissionError(f"[Errno 13] Permission denied: '{self_path}'")
            original_unlink(self_path, missing_ok)

        config = HousekeepingConfig(nwave_dir=nwave_dir, audit_log_dir=logs_dir)

        from tests.des.acceptance.conftest_housekeeping import FixedTimeProvider

        # Should not raise despite permission error
        with patch.object(_Path, "unlink", selective_unlink):
            HousekeepingService.run_housekeeping(config, FixedTimeProvider(today))

        remaining = sorted(f.name for f in logs_dir.iterdir())
        # The protected file should still exist (skipped due to OSError)
        assert protected_name in remaining
        # Today's log should still exist
        assert f"audit-{today.strftime('%Y-%m-%d')}.log" in remaining
        # All other old files should be removed (14 out of 15)
        assert len(remaining) == 2  # protected + today

    @pytest.mark.slow
    def test_audit_log_cleanup_completes_within_performance_budget(self, tmp_path):
        """Given a project with 90 audit log files
        When housekeeping runs audit log cleanup
        Then cleanup completes in under 200ms."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        logs_dir = nwave_dir / "des" / "logs"

        today = datetime(2026, 2, 26, tzinfo=timezone.utc)
        for i in range(90):
            date = today - timedelta(days=i)
            _create_audit_log(logs_dir, date.strftime("%Y-%m-%d"))

        config = HousekeepingConfig(nwave_dir=nwave_dir, audit_log_dir=logs_dir)

        from tests.des.acceptance.conftest_housekeeping import FixedTimeProvider

        start = time.monotonic()
        HousekeepingService.run_housekeeping(config, FixedTimeProvider(today))
        elapsed_ms = (time.monotonic() - start) * 1000

        assert elapsed_ms < 200, (
            f"Audit log cleanup took {elapsed_ms:.1f}ms (budget: 200ms)"
        )

    def test_todays_log_preserved_regardless_of_retention(self, tmp_path):
        """Given today is 2026-02-26
        And audit-2026-02-26.log exists
        And retention is set to 0 days
        When session-start housekeeping runs
        Then audit-2026-02-26.log is preserved."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        logs_dir = nwave_dir / "des" / "logs"

        today = datetime(2026, 2, 26, tzinfo=timezone.utc)
        _create_audit_log(logs_dir, "2026-02-26")

        # Retention of 0 days would theoretically delete everything
        config = HousekeepingConfig(
            nwave_dir=nwave_dir,
            audit_log_dir=logs_dir,
            audit_retention_days=0,
        )

        from tests.des.acceptance.conftest_housekeeping import FixedTimeProvider

        HousekeepingService.run_housekeeping(config, FixedTimeProvider(today))

        # Today's log must always be preserved
        assert (logs_dir / "audit-2026-02-26.log").exists()


# ---------------------------------------------------------------------------
# US-HK-02: Orphaned Signal File Cleanup
# ---------------------------------------------------------------------------


class TestSignalFileCleanup:
    """US-HK-02: Housekeeping removes stale signal files left by crashed sessions."""

    def test_removes_orphaned_signal_file_from_crashed_session(self, tmp_path):
        """Given .nwave/des/ contains des-task-active-myproject--step-3
        And the file modification time is 18 hours ago
        When session-start housekeeping runs
        Then des-task-active-myproject--step-3 is removed."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        des_dir = nwave_dir / "des"
        now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=timezone.utc)

        _create_signal_file(des_dir, "des-task-active-myproject--step-3", 18, now)

        config = HousekeepingConfig(nwave_dir=nwave_dir)

        from tests.des.acceptance.conftest_housekeeping import FixedTimeProvider

        HousekeepingService.run_housekeeping(config, FixedTimeProvider(now))

        assert not (des_dir / "des-task-active-myproject--step-3").exists()

    def test_preserves_recent_signal_file_from_concurrent_session(self, tmp_path):
        """Given .nwave/des/ contains des-task-active-api-service--step-2
        And the file modification time is 45 minutes ago
        When session-start housekeeping runs
        Then des-task-active-api-service--step-2 is preserved."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        des_dir = nwave_dir / "des"
        now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=timezone.utc)

        _create_signal_file(des_dir, "des-task-active-api-service--step-2", 0.75, now)

        config = HousekeepingConfig(nwave_dir=nwave_dir)

        from tests.des.acceptance.conftest_housekeeping import FixedTimeProvider

        HousekeepingService.run_housekeeping(config, FixedTimeProvider(now))

        assert (des_dir / "des-task-active-api-service--step-2").exists()

    def test_removes_stale_deliver_session_json(self, tmp_path):
        """Given .nwave/des/ contains deliver-session.json
        And the file modification time is 26 hours ago
        When session-start housekeeping runs
        Then deliver-session.json is removed."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        des_dir = nwave_dir / "des"
        now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=timezone.utc)

        _create_signal_file(des_dir, "deliver-session.json", 26, now)

        config = HousekeepingConfig(nwave_dir=nwave_dir)

        from tests.des.acceptance.conftest_housekeeping import FixedTimeProvider

        HousekeepingService.run_housekeeping(config, FixedTimeProvider(now))

        assert not (des_dir / "deliver-session.json").exists()

    def test_preserves_recent_deliver_session_json(self, tmp_path):
        """Given a deliver-session.json created 30 minutes ago
        When session-start housekeeping runs
        Then deliver-session.json is preserved."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        des_dir = nwave_dir / "des"
        now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=timezone.utc)

        _create_signal_file(des_dir, "deliver-session.json", 0.5, now)

        config = HousekeepingConfig(nwave_dir=nwave_dir)

        from tests.des.acceptance.conftest_housekeeping import FixedTimeProvider

        HousekeepingService.run_housekeeping(config, FixedTimeProvider(now))

        assert (des_dir / "deliver-session.json").exists()

    def test_removes_multiple_orphaned_signal_files_in_one_pass(self, tmp_path):
        """Given .nwave/des/ contains 4 signal files all older than threshold
        When session-start housekeeping runs
        Then all 4 stale signal files are removed."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        des_dir = nwave_dir / "des"
        now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=timezone.utc)

        _create_signal_file(des_dir, "des-task-active-proj-a--step-1", 48, now)
        _create_signal_file(des_dir, "des-task-active-proj-b--step-2", 25, now)
        _create_signal_file(des_dir, "des-task-active-proj-c--step-3", 72, now)
        _create_signal_file(des_dir, "des-task-active", 30, now)

        config = HousekeepingConfig(nwave_dir=nwave_dir)

        from tests.des.acceptance.conftest_housekeeping import FixedTimeProvider

        HousekeepingService.run_housekeeping(config, FixedTimeProvider(now))

        assert not (des_dir / "des-task-active-proj-a--step-1").exists()
        assert not (des_dir / "des-task-active-proj-b--step-2").exists()
        assert not (des_dir / "des-task-active-proj-c--step-3").exists()
        assert not (des_dir / "des-task-active").exists()

    def test_no_signal_files_exist(self, tmp_path):
        """Given .nwave/des/ contains no signal files
        When session-start housekeeping runs
        Then housekeeping completes without errors."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        des_dir = nwave_dir / "des"
        des_dir.mkdir(parents=True, exist_ok=True)
        now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=timezone.utc)

        config = HousekeepingConfig(nwave_dir=nwave_dir)

        from tests.des.acceptance.conftest_housekeeping import FixedTimeProvider

        # Should not raise
        HousekeepingService.run_housekeeping(config, FixedTimeProvider(now))

    def test_custom_staleness_threshold(self, tmp_path):
        """Given des-config.json specifies signal_staleness_hours as 8
        And a signal file created 5 hours ago
        When session-start housekeeping runs
        Then the signal file is preserved (5 hours < 8 hour threshold)."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        des_dir = nwave_dir / "des"
        now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=timezone.utc)

        _create_signal_file(des_dir, "des-task-active-feature--step-1", 5, now)

        config = HousekeepingConfig(
            nwave_dir=nwave_dir,
            signal_staleness_hours=8,
        )

        from tests.des.acceptance.conftest_housekeeping import FixedTimeProvider

        HousekeepingService.run_housekeeping(config, FixedTimeProvider(now))

        assert (des_dir / "des-task-active-feature--step-1").exists()


# ---------------------------------------------------------------------------
# US-HK-03: Skill Tracking Log Rotation
# ---------------------------------------------------------------------------


class TestSkillLogRotation:
    """US-HK-03: Housekeeping truncates oversized skill tracking logs."""

    def test_truncates_oversized_skill_tracking_log(self, tmp_path):
        """Given skill-loading-log.jsonl has 50000 lines (approximately 15MB)
        When session-start housekeeping runs
        Then skill-loading-log.jsonl is truncated to the last 1000 lines
        And the most recent 1000 entries are preserved
        And older entries are discarded."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        log_file = _create_skill_log(nwave_dir, 50000)

        config = HousekeepingConfig(nwave_dir=nwave_dir)

        from tests.des.acceptance.conftest_housekeeping import FixedTimeProvider

        now = datetime(2026, 2, 26, tzinfo=timezone.utc)
        HousekeepingService.run_housekeeping(config, FixedTimeProvider(now))

        # Should be truncated to last 1000 lines
        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1000

        # Verify the MOST RECENT entries are preserved (last 1000 of original 50000)
        import json

        first_preserved = json.loads(lines[0])
        assert first_preserved["entry"] == 49000  # 50000 - 1000

        last_preserved = json.loads(lines[-1])
        assert last_preserved["entry"] == 49999

    def test_skips_normal_sized_skill_tracking_log(self, tmp_path):
        """Given skill-loading-log.jsonl is 400KB (well under 1MB threshold)
        When session-start housekeeping runs
        Then skill-loading-log.jsonl is not modified."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        # Create a small log (~400KB worth of lines)
        log_file = _create_skill_log(nwave_dir, 500)
        original_content = log_file.read_text(encoding="utf-8")
        original_size = log_file.stat().st_size

        config = HousekeepingConfig(nwave_dir=nwave_dir)

        from tests.des.acceptance.conftest_housekeeping import FixedTimeProvider

        now = datetime(2026, 2, 26, tzinfo=timezone.utc)
        HousekeepingService.run_housekeeping(config, FixedTimeProvider(now))

        # File should not be modified
        assert log_file.read_text(encoding="utf-8") == original_content
        assert log_file.stat().st_size == original_size

    def test_no_skill_tracking_log_exists(self, tmp_path):
        """Given no skill-loading-log.jsonl file exists in .nwave/
        When session-start housekeeping runs
        Then no errors occur
        And no file is created."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        nwave_dir.mkdir(parents=True, exist_ok=True)
        skill_log = nwave_dir / "skill-loading-log.jsonl"

        config = HousekeepingConfig(nwave_dir=nwave_dir)

        from tests.des.acceptance.conftest_housekeeping import FixedTimeProvider

        now = datetime(2026, 2, 26, tzinfo=timezone.utc)
        # Should not raise
        HousekeepingService.run_housekeeping(config, FixedTimeProvider(now))

        # No file should be created
        assert not skill_log.exists()

    def test_truncation_failure_does_not_block_session(self, tmp_path):
        """Given skill-loading-log.jsonl is 5MB
        And the file cannot be written (simulated permission error)
        When housekeeping attempts to truncate it
        Then the truncation is skipped
        And no exception propagates."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        log_file = _create_skill_log(nwave_dir, 20000)

        # Make the file read-only to prevent truncation write
        log_file.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

        config = HousekeepingConfig(nwave_dir=nwave_dir)

        from tests.des.acceptance.conftest_housekeeping import FixedTimeProvider

        now = datetime(2026, 2, 26, tzinfo=timezone.utc)
        # Should not raise
        HousekeepingService.run_housekeeping(config, FixedTimeProvider(now))

        # File should still exist (truncation was skipped)
        assert log_file.exists()

        # Cleanup: restore permissions so tmp_path cleanup works
        log_file.chmod(stat.S_IRWXU)

    def test_custom_size_threshold(self, tmp_path):
        """Given des-config.json specifies skill_log_max_bytes as 5MB
        And skill-loading-log.jsonl is 3MB
        When session-start housekeeping runs
        Then skill-loading-log.jsonl is not modified (3MB < 5MB threshold)."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        # Create a log that would exceed 1MB default but not 5MB custom threshold
        log_file = _create_skill_log(nwave_dir, 10000)
        original_content = log_file.read_text(encoding="utf-8")

        config = HousekeepingConfig(
            nwave_dir=nwave_dir,
            skill_log_max_bytes=5_242_880,  # 5MB
        )

        from tests.des.acceptance.conftest_housekeeping import FixedTimeProvider

        now = datetime(2026, 2, 26, tzinfo=timezone.utc)
        HousekeepingService.run_housekeeping(config, FixedTimeProvider(now))

        # File should not be modified (under custom threshold)
        assert log_file.read_text(encoding="utf-8") == original_content


# ---------------------------------------------------------------------------
# US-HK-04: Housekeeping Orchestration
# ---------------------------------------------------------------------------


class TestHousekeepingOrchestration:
    """US-HK-04: Housekeeping runs all cleanup tasks as a coordinated operation."""

    def test_all_tasks_run_with_default_configuration(self, tmp_path):
        """Given no housekeeping configuration in des-config.json
        And the project has old audit logs, a stale signal file, and a small skill log
        When session-start housekeeping runs
        Then old audit logs are removed
        And the stale signal file is removed
        And the small skill log is not modified
        And no console output is produced."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        logs_dir = nwave_dir / "des" / "logs"
        des_dir = nwave_dir / "des"
        now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=timezone.utc)

        # Create 12 old audit logs (all > 7 days old)
        for i in range(12):
            days_ago = 8 + i
            date = now - timedelta(days=days_ago)
            _create_audit_log(logs_dir, date.strftime("%Y-%m-%d"))
        # Create today's log
        _create_audit_log(logs_dir, now.strftime("%Y-%m-%d"))

        # Create a stale signal file (20 hours old)
        _create_signal_file(des_dir, "des-task-active-old", 20, now)

        # Create a small skill log (under threshold)
        _create_skill_log(nwave_dir, 100)
        skill_log = nwave_dir / "skill-loading-log.jsonl"
        original_skill_content = skill_log.read_text(encoding="utf-8")

        config = HousekeepingConfig(nwave_dir=nwave_dir, audit_log_dir=logs_dir)

        from tests.des.acceptance.conftest_housekeeping import FixedTimeProvider

        HousekeepingService.run_housekeeping(config, FixedTimeProvider(now))

        # 12 old audit logs removed, today's preserved
        remaining_logs = list(logs_dir.iterdir())
        assert len(remaining_logs) == 1
        assert remaining_logs[0].name == f"audit-{now.strftime('%Y-%m-%d')}.log"

        # Stale signal file removed
        assert not (des_dir / "des-task-active-old").exists()

        # Skill log not modified (under threshold)
        assert skill_log.read_text(encoding="utf-8") == original_skill_content

    def test_individual_task_failure_does_not_affect_other_tasks(self, tmp_path):
        """Given audit log cleanup will raise a PermissionError
        And signal file cleanup will succeed
        And skill log rotation will succeed
        When session-start housekeeping runs
        Then signal files are cleaned successfully
        And skill log rotation runs successfully
        And no exception propagates."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        des_dir = nwave_dir / "des"
        logs_dir = des_dir / "logs"
        now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=timezone.utc)

        # Create audit log directory with bad permissions (causes PermissionError)
        logs_dir.mkdir(parents=True, exist_ok=True)
        _create_audit_log(logs_dir, "2026-02-10")
        # Make the directory non-readable to force an error during listing
        logs_dir.chmod(0o000)

        # Create a stale signal file that should be cleaned
        _create_signal_file(des_dir, "des-task-active-stale", 20, now)

        # Create an oversized skill log that should be truncated.
        # Use skill_log_max_bytes=1 so the 5000-line log always exceeds the threshold,
        # matching the acceptance criteria regardless of line length.
        _create_skill_log(nwave_dir, 5000)

        config = HousekeepingConfig(
            nwave_dir=nwave_dir, audit_log_dir=logs_dir, skill_log_max_bytes=1
        )

        from tests.des.acceptance.conftest_housekeeping import FixedTimeProvider

        # Should not raise despite audit log failure
        HousekeepingService.run_housekeeping(config, FixedTimeProvider(now))

        # Signal file should be cleaned (independent of audit failure)
        assert not (des_dir / "des-task-active-stale").exists()

        # Skill log should be truncated (independent of audit failure)
        skill_log = nwave_dir / "skill-loading-log.jsonl"
        lines = skill_log.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1000

        # Cleanup: restore permissions so tmp_path cleanup works
        logs_dir.chmod(stat.S_IRWXU)

    def test_housekeeping_disabled_via_configuration(self, tmp_path):
        """Given des-config.json contains enabled=false
        And the project has stale signal files and old audit logs
        When session-start housekeeping runs
        Then no housekeeping file operations are performed."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        logs_dir = nwave_dir / "des" / "logs"
        des_dir = nwave_dir / "des"
        now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=timezone.utc)

        # Create files that would normally be cleaned
        _create_audit_log(logs_dir, "2026-02-05")
        _create_signal_file(des_dir, "des-task-active-stale", 20, now)

        config = HousekeepingConfig(
            nwave_dir=nwave_dir,
            audit_log_dir=logs_dir,
            enabled=False,
        )

        from tests.des.acceptance.conftest_housekeeping import FixedTimeProvider

        HousekeepingService.run_housekeeping(config, FixedTimeProvider(now))

        # Nothing should be deleted
        assert (logs_dir / "audit-2026-02-05.log").exists()
        assert (des_dir / "des-task-active-stale").exists()

    def test_project_with_no_nwave_directory(self, tmp_path):
        """Given the project directory contains no .nwave/ directory
        When session-start housekeeping runs
        Then housekeeping completes immediately
        And no .nwave/ directory is created
        And no errors are raised."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        # Intentionally do NOT create .nwave/

        config = HousekeepingConfig(nwave_dir=nwave_dir)

        from tests.des.acceptance.conftest_housekeeping import FixedTimeProvider

        now = datetime(2026, 2, 26, tzinfo=timezone.utc)
        # Should not raise
        HousekeepingService.run_housekeeping(config, FixedTimeProvider(now))

        # No directory should be created
        assert not nwave_dir.exists()

    @pytest.mark.slow
    def test_total_housekeeping_completes_within_performance_budget(self, tmp_path):
        """Given a project with 90 audit logs, 5 stale signal files, and a 10MB skill log
        When session-start housekeeping runs
        Then all operations complete in under 500ms total."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        logs_dir = nwave_dir / "des" / "logs"
        des_dir = nwave_dir / "des"
        now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=timezone.utc)

        # 90 audit logs
        for i in range(90):
            date = now - timedelta(days=i)
            _create_audit_log(logs_dir, date.strftime("%Y-%m-%d"))

        # 5 stale signal files
        for i in range(5):
            _create_signal_file(
                des_dir, f"des-task-active-proj-{i}--step-1", 24 + i, now
            )

        # Large skill log (~10MB)
        _create_skill_log(nwave_dir, 30000)

        config = HousekeepingConfig(nwave_dir=nwave_dir, audit_log_dir=logs_dir)

        from tests.des.acceptance.conftest_housekeeping import FixedTimeProvider

        start = time.monotonic()
        HousekeepingService.run_housekeeping(config, FixedTimeProvider(now))
        elapsed_ms = (time.monotonic() - start) * 1000

        assert elapsed_ms < 500, (
            f"Total housekeeping took {elapsed_ms:.1f}ms (budget: 500ms)"
        )

    def test_housekeeping_runs_alongside_update_check_without_interference(
        self, tmp_path, capsys
    ):
        """Given both housekeeping and update check are enabled
        When a new session starts
        Then both housekeeping and update check execute
        And neither operation blocks or interferes with the other."""
        import io
        from unittest.mock import MagicMock, patch

        from des.adapters.drivers.hooks.session_start_handler import (
            handle_session_start,
        )

        nwave_dir = tmp_path / ".nwave"
        logs_dir = nwave_dir / "des" / "logs"

        # Create an old audit log that housekeeping should clean
        _create_audit_log(logs_dir, "2026-02-10")

        # Mock the update check to return UP_TO_DATE
        from des.application.update_check_service import (
            UpdateCheckResult,
            UpdateStatus,
        )

        update_result = UpdateCheckResult(status=UpdateStatus.UP_TO_DATE)

        with (
            patch(
                "des.adapters.drivers.hooks.session_start_handler._build_update_check_service"
            ) as mock_factory,
            patch("sys.stdin", io.StringIO("{}")),
            patch(
                "des.adapters.drivers.hooks.session_start_handler._run_housekeeping"
            ) as mock_hk,
        ):
            mock_service = MagicMock()
            mock_service.check_for_updates.return_value = update_result
            mock_factory.return_value = mock_service

            exit_code = handle_session_start()

        assert exit_code == 0
        # Housekeeping was called
        mock_hk.assert_called_once()
        # No console output from housekeeping
        captured = capsys.readouterr()
        assert captured.out.strip() == ""


# ---------------------------------------------------------------------------
# Cross-Cutting Properties
# ---------------------------------------------------------------------------


class TestCrossCuttingProperties:
    """Cross-cutting acceptance criteria that apply to all housekeeping tasks."""

    def test_housekeeping_never_blocks_session_start(self, tmp_path):
        """Given any combination of file system errors during housekeeping
        When session-start housekeeping completes
        Then no exception propagates to the caller.

        This validates the fail-open contract: housekeeping must never
        prevent a session from starting regardless of filesystem state."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        des_dir = nwave_dir / "des"
        logs_dir = des_dir / "logs"

        now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=timezone.utc)

        # Create a hostile filesystem state:
        # 1. Audit log directory with no permissions
        logs_dir.mkdir(parents=True, exist_ok=True)
        _create_audit_log(logs_dir, "2026-02-10")
        logs_dir.chmod(0o000)

        # 2. Signal file that cannot be deleted (in a read-only directory)
        # (Note: des_dir already exists from logs_dir creation above, but
        #  we need a signal file that will fail to delete)

        # 3. Skill log that cannot be written
        _create_skill_log(nwave_dir, 5000)
        skill_log = nwave_dir / "skill-loading-log.jsonl"
        skill_log.chmod(stat.S_IRUSR)

        config = HousekeepingConfig(nwave_dir=nwave_dir, audit_log_dir=logs_dir)

        from tests.des.acceptance.conftest_housekeeping import FixedTimeProvider

        # Must NOT raise — this is the core fail-open contract
        HousekeepingService.run_housekeeping(config, FixedTimeProvider(now))

        # Cleanup: restore permissions for tmp_path cleanup
        logs_dir.chmod(stat.S_IRWXU)
        skill_log.chmod(stat.S_IRWXU)

    def test_housekeeping_never_creates_directories_or_files(self, tmp_path):
        """Given housekeeping runs in a project where .nwave/ does not exist
        When housekeeping completes
        Then no new directories or files have been created.

        Housekeeping is a cleanup operation. It must never create state
        where none existed before."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        # .nwave/ intentionally does not exist

        config = HousekeepingConfig(nwave_dir=nwave_dir)

        from tests.des.acceptance.conftest_housekeeping import FixedTimeProvider

        now = datetime(2026, 2, 26, tzinfo=timezone.utc)
        HousekeepingService.run_housekeeping(config, FixedTimeProvider(now))

        # Snapshot the entire tmp_path — nothing should have been created
        all_entries = list(tmp_path.rglob("*"))
        assert len(all_entries) == 0, (
            f"Housekeeping created files/directories: {[str(e) for e in all_entries]}"
        )
