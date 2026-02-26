"""
Unit tests for HousekeepingService orchestration shell.

Tests enter through the driving port: HousekeepingService.run_housekeeping().
Task stubs (_clean_audit_logs, _clean_signal_files, _rotate_skill_log) are
patched at the class boundary to verify orchestration behavior.

Test Budget: 4 distinct behaviors x 2 = 8 max. Actual: 4 tests.

Behaviors:
  1. Disabled config -> no tasks run
  2. Missing nwave_dir -> returns immediately
  3. Task exception -> other tasks still run (fail-isolation)
  4. No console output under any condition
"""

from __future__ import annotations

from datetime import datetime, timezone
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
        """Given enabled=False, no task methods are called."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        nwave_dir.mkdir()
        config = HousekeepingConfig(nwave_dir=nwave_dir, enabled=False)
        time_provider = FixedTimeProvider(_NOW)

        with (
            patch.object(HousekeepingService, "_clean_audit_logs") as mock_audit,
            patch.object(HousekeepingService, "_clean_signal_files") as mock_signal,
            patch.object(HousekeepingService, "_rotate_skill_log") as mock_skill,
        ):
            HousekeepingService.run_housekeeping(config, time_provider)

        mock_audit.assert_not_called()
        mock_signal.assert_not_called()
        mock_skill.assert_not_called()

    def test_missing_nwave_dir_skips_all_tasks(self, tmp_path: Path) -> None:
        """Given nwave_dir does not exist, no task methods are called."""
        from des.application.housekeeping_service import (
            HousekeepingConfig,
            HousekeepingService,
        )

        nwave_dir = tmp_path / ".nwave"
        # Intentionally not created
        config = HousekeepingConfig(nwave_dir=nwave_dir)
        time_provider = FixedTimeProvider(_NOW)

        with (
            patch.object(HousekeepingService, "_clean_audit_logs") as mock_audit,
            patch.object(HousekeepingService, "_clean_signal_files") as mock_signal,
            patch.object(HousekeepingService, "_rotate_skill_log") as mock_skill,
        ):
            HousekeepingService.run_housekeeping(config, time_provider)

        mock_audit.assert_not_called()
        mock_signal.assert_not_called()
        mock_skill.assert_not_called()

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
