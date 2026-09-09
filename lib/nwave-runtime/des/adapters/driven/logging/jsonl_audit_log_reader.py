"""JsonlAuditLogReader - driven adapter for reading audit events.

Implements the AuditLogReader port by reading JSONL files.
Uses the same log directory resolution as JsonlAuditLogWriter.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from des.domain.audit_log_path_resolver import AuditLogPathResolver
from des.ports.driven_ports.audit_log_reader import AuditLogReader


if TYPE_CHECKING:
    from pathlib import Path


class JsonlAuditLogReader(AuditLogReader):
    """Reads audit events from JSONL files.

    Scans today's log file backward to find the most recent matching entry,
    falling back to yesterday's (UTC) file when today's has no match -- a
    write just before UTC midnight and a read just after must not be missed
    just because the two land in different date-rotated files.
    Uses shared AuditLogPathResolver for consistent path resolution with writer.
    """

    def __init__(
        self, log_dir: str | Path | None = None, cwd: str | Path | None = None
    ) -> None:
        resolved = AuditLogPathResolver(log_dir=log_dir, cwd=cwd).resolve()
        self._log_dir = resolved

    def read_last_entry(
        self,
        event_type: str | None = None,
        feature_name: str | None = None,
        step_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Read the most recent audit entry matching the given filters.

        Scans today's log file from end to start for efficiency, falling back
        to yesterday's file when today's has no match (or does not exist yet).
        The writer and reader rotate independently on UTC-date, so a write
        just before UTC midnight and a read just after would otherwise land
        in different files and the entry would be missed (GDP-6: a miss must
        not be indistinguishable from "nothing happened").

        Returns:
            Most recent matching entry as dict, or None if not found in
            either of today's or yesterday's log file.
        """
        for log_file in self._candidate_log_files():
            entry = self._last_matching_entry_in(
                log_file, event_type, feature_name, step_id
            )
            if entry is not None:
                return entry
        return None

    def _last_matching_entry_in(
        self,
        log_file: Path | None,
        event_type: str | None,
        feature_name: str | None,
        step_id: str | None,
    ) -> dict[str, Any] | None:
        """Scan a single log file backward for the most recent match, else None."""
        if log_file is None or not log_file.exists():
            return None

        try:
            lines = log_file.read_text().strip().splitlines()
        except (OSError, PermissionError):
            return None

        # Scan backward for most recent match
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if self._matches(entry, event_type, feature_name, step_id):
                return entry

        return None

    def _matches(
        self,
        entry: dict,
        event_type: str | None,
        feature_name: str | None,
        step_id: str | None,
    ) -> bool:
        """Check if entry matches all provided filters."""
        if event_type and entry.get("event") != event_type:
            return False
        if feature_name and entry.get("feature_name") != feature_name:
            return False
        return not (step_id and entry.get("step_id") != step_id)

    def _candidate_log_files(self) -> list[Path]:
        """Today's and yesterday's (UTC) log file paths, most-recent first.

        Returns an empty list if the log directory does not exist. Neither
        candidate is checked for existence here -- that is
        `_last_matching_entry_in`'s job, kept a single responsibility.
        """
        if not self._log_dir.exists():
            return []
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        return [
            self._log_dir / f"audit-{today}.log",
            self._log_dir / f"audit-{yesterday}.log",
        ]
