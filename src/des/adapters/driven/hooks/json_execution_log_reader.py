"""JsonExecutionLogReader - driven adapter for reading execution log data.

Implements the ExecutionLogReader port by reading JSON execution-log files
and converting event entries into domain PhaseEvent objects.

Supports two event formats via PhaseEventParser.parse_auto():
- v2.0: pipe-delimited strings ("step_id|phase|status|data|timestamp")
- v3.0: structured JSON dicts ({sid, p, s, d, t} with optional tu, tk)

Infrastructure details (JSON format, file I/O) are hidden behind the port interface.
The application layer only sees PhaseEvent domain objects.
"""

from __future__ import annotations

import json

from des.domain.phase_event import PhaseEvent, PhaseEventParser
from des.ports.driven_ports.execution_log_reader import (
    ExecutionLogReader,
    LogFileCorrupted,
    LogFileNotFound,
)


class JsonExecutionLogReader(ExecutionLogReader):
    """Reads execution log data from JSON files.

    Supports both v2.0 (pipe-delimited) and v3.0 (structured dict) formats.
    Format auto-detection is per-event via PhaseEventParser.parse_auto().

    File format (Schema v2.0 - pipe-delimited strings):
        {"schema_version": "2.0", "events": ["01-01|PREPARE|EXECUTED|PASS|2026-02-02T10:00:00Z"]}

    File format (Schema v3.0 - structured JSON objects):
        {"schema_version": "3.0", "events": [{"sid": "01-01", "p": "PREPARE", ...}]}
    """

    def __init__(self) -> None:
        self._parser = PhaseEventParser()

    def read_project_id(self, log_path: str) -> str | None:
        """Read the project_id from the execution log.

        Args:
            log_path: Absolute path to the execution log file

        Returns:
            Project ID string, or None if not found in the log

        Raises:
            LogFileNotFound: If the log file does not exist
            LogFileCorrupted: If the log file cannot be parsed
        """
        data = self._load_json(log_path)
        # Schema v3.0 uses "feature_id"; fall back to "project_id" for compat
        return data.get("feature_id") or data.get("project_id")

    def read_step_events(self, log_path: str, step_id: str) -> list[PhaseEvent]:
        """Read and parse phase events for a specific step.

        Translates raw JSON event entries (strings or dicts) into domain
        PhaseEvent objects using PhaseEventParser, filtered by step_id.

        Args:
            log_path: Absolute path to the execution log file
            step_id: Step identifier to filter events for

        Returns:
            List of PhaseEvent objects matching the step_id

        Raises:
            LogFileNotFound: If the log file does not exist
            LogFileCorrupted: If the log file cannot be parsed
        """
        data = self._load_json(log_path)
        raw_events = data.get("events", [])
        return self._parser.parse_many(raw_events, step_id)

    def read_all_events(self, log_path: str) -> list[PhaseEvent]:
        """Read and parse all phase events without step_id filtering.

        Args:
            log_path: Absolute path to the execution log file

        Returns:
            List of all PhaseEvent objects in the log

        Raises:
            LogFileNotFound: If the log file does not exist
            LogFileCorrupted: If the log file cannot be parsed
        """
        data = self._load_json(log_path)
        raw_events = data.get("events", [])
        return self._parser.parse_all(raw_events)

    def _load_json(self, log_path: str) -> dict:
        """Load and parse a JSON file.

        Args:
            log_path: Absolute path to the JSON file

        Returns:
            Parsed JSON data as a dictionary

        Raises:
            LogFileNotFound: If the file does not exist
            LogFileCorrupted: If the JSON cannot be parsed
        """
        try:
            with open(log_path, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            raise LogFileNotFound(f"Execution log not found: {log_path}")
        except json.JSONDecodeError as e:
            raise LogFileCorrupted(f"Invalid JSON in execution log: {e}")

        if not isinstance(data, dict):
            raise LogFileCorrupted(
                f"Execution log must be a JSON object, got {type(data).__name__}"
            )

        return data


# Backward-compatible alias
YamlExecutionLogReader = JsonExecutionLogReader
