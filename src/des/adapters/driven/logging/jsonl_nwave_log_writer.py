"""JsonlNWaveLogWriter - driven adapter for nWave observability logging.

Implements the NWaveLogWriter port by appending structured log entries
to daily JSONL files under ~/.nwave/logs/.

Features:
- Compact JSONL output (one JSON object per line)
- Daily log rotation with date-based naming (nwave-YYYY-MM-DD.jsonl)
- Level-based filtering (entries below threshold are discarded)
- Exception swallowing (logging must never break operations)
- Auto-creates log directory if missing
"""

from __future__ import annotations

import json
from pathlib import Path

from des.ports.driven_ports.nwave_log_writer import (
    LogLevel,
    NWaveLogEntry,
    NWaveLogWriter,
)


class JsonlNWaveLogWriter(NWaveLogWriter):
    """Writes structured log entries to daily JSONL files.

    Each entry is serialized as one compact JSON line, appended to a
    daily log file. File format: nwave-YYYY-MM-DD.jsonl in the
    configured log directory.

    Never raises exceptions -- all I/O errors are silently swallowed
    to ensure logging cannot break operations.
    """

    def __init__(
        self,
        log_dir: str | Path | None = None,
        level: LogLevel = LogLevel.INFO,
    ) -> None:
        """Initialize with a log directory and minimum level.

        Args:
            log_dir: Directory for log files. Defaults to ~/.nwave/logs/.
            level: Minimum severity level to log. Defaults to INFO.
        """
        if log_dir is None:
            self._log_dir = Path.home() / ".nwave" / "logs"
        else:
            self._log_dir = Path(log_dir)
        self._level = level

    def log(self, entry: NWaveLogEntry) -> None:
        """Write a single log entry to the daily JSONL file.

        Entries below the configured minimum level are silently discarded.
        Any I/O errors are swallowed to ensure logging never breaks operations.

        Args:
            entry: The structured log entry to write.
        """
        try:
            if entry.level < self._level:
                return

            self._log_dir.mkdir(parents=True, exist_ok=True)

            record: dict = {
                "timestamp": entry.timestamp,
                "level": entry.level.name,
                "stage": entry.stage,
                "operation": entry.operation,
                "event": entry.event,
                "message": entry.message,
                "operation_id": entry.operation_id,
            }

            if entry.error_code is not None:
                record["error_code"] = entry.error_code
            if entry.duration_ms is not None:
                record["duration_ms"] = entry.duration_ms
            if entry.context:
                record["context"] = entry.context

            json_line = json.dumps(record, separators=(",", ":"))

            date_part = entry.timestamp[:10]
            log_file = self._log_dir / f"nwave-{date_part}.jsonl"

            with open(log_file, "a") as f:
                f.write(json_line + "\n")

        except Exception:
            pass

    def set_level(self, level: LogLevel) -> None:
        """Set the minimum log level for filtering.

        Args:
            level: The minimum severity level to log.
        """
        self._level = level
