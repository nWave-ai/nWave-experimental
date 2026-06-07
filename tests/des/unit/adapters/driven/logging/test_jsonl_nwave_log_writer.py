"""Unit tests for JsonlNWaveLogWriter and NullNWaveLogWriter adapters.

Step 01-02: JSONL and null log writer adapters for NWaveLogWriter port.

Test Budget: 5 behaviors x 2 = 10 max unit tests.

Behaviors:
1. JSONL file writing (compact JSON lines with correct filename)
2. Auto-create log directory
3. Level filtering (discard entries below threshold)
4. Exception swallowing (never raises)
5. Null writer no-op
"""

import json

import pytest

from des.ports.driven_ports.nwave_log_writer import (
    LogLevel,
    NWaveLogEntry,
    NWaveLogWriter,
)


def _make_entry(
    *,
    level: LogLevel = LogLevel.INFO,
    timestamp: str = "2026-03-15T10:00:00.000Z",
    stage: str = "hook",
    operation: str = "pre_tool_use",
    event: str = "entry",
    message: str = "Test log message",
    operation_id: str = "op-001",
    error_code: str | None = None,
    duration_ms: float | None = None,
    context: dict | None = None,
) -> NWaveLogEntry:
    """Create a test NWaveLogEntry with sensible defaults."""
    return NWaveLogEntry(
        timestamp=timestamp,
        level=level,
        stage=stage,
        operation=operation,
        event=event,
        message=message,
        operation_id=operation_id,
        error_code=error_code,
        duration_ms=duration_ms,
        context=context or {},
    )


def _read_jsonl_lines(directory, prefix="nwave-") -> list[dict]:
    """Read all JSONL entries from files matching the prefix in directory."""
    entries = []
    if not directory.exists():
        return entries
    for log_file in sorted(directory.iterdir()):
        if log_file.name.startswith(prefix) and log_file.suffix == ".jsonl":
            for line in log_file.read_text().strip().split("\n"):
                if line.strip():
                    entries.append(json.loads(line))
    return entries


# ---------------------------------------------------------------------------
# JsonlNWaveLogWriter Tests
# ---------------------------------------------------------------------------


class TestJsonlNWaveLogWriterWritesJsonlEntries:
    """AC1: JsonlNWaveLogWriter appends compact JSON lines to daily JSONL file."""

    def test_writes_entry_to_daily_jsonl_file_with_correct_name(self, tmp_path):
        """Entry written to nwave-YYYY-MM-DD.jsonl based on entry timestamp."""
        from des.adapters.driven.logging.jsonl_nwave_log_writer import (
            JsonlNWaveLogWriter,
        )

        log_dir = tmp_path / "logs"
        writer = JsonlNWaveLogWriter(log_dir=log_dir)

        writer.log(_make_entry(timestamp="2026-03-15T10:00:00.000Z"))

        expected_file = log_dir / "nwave-2026-03-15.jsonl"
        assert expected_file.exists()
        entries = _read_jsonl_lines(log_dir)
        assert len(entries) == 1
        assert entries[0]["message"] == "Test log message"
        assert entries[0]["level"] == "INFO"
        assert entries[0]["stage"] == "hook"
        assert entries[0]["operation"] == "pre_tool_use"
        assert entries[0]["event"] == "entry"
        assert entries[0]["operation_id"] == "op-001"

    def test_appends_multiple_entries_as_separate_lines(self, tmp_path):
        """Multiple log calls append to the same daily file as separate lines."""
        from des.adapters.driven.logging.jsonl_nwave_log_writer import (
            JsonlNWaveLogWriter,
        )

        log_dir = tmp_path / "logs"
        writer = JsonlNWaveLogWriter(log_dir=log_dir)

        writer.log(_make_entry(message="First entry"))
        writer.log(_make_entry(message="Second entry"))

        entries = _read_jsonl_lines(log_dir)
        assert len(entries) == 2
        assert entries[0]["message"] == "First entry"
        assert entries[1]["message"] == "Second entry"

    def test_writes_compact_json_without_whitespace(self, tmp_path):
        """Compact JSON: separators=(',', ':'), no extra whitespace."""
        from des.adapters.driven.logging.jsonl_nwave_log_writer import (
            JsonlNWaveLogWriter,
        )

        log_dir = tmp_path / "logs"
        writer = JsonlNWaveLogWriter(log_dir=log_dir)

        writer.log(_make_entry())

        log_file = log_dir / "nwave-2026-03-15.jsonl"
        raw_line = log_file.read_text().strip().split("\n")[0]
        # Compact format: no spaces after colons or commas
        assert ": " not in raw_line
        assert ", " not in raw_line

    def test_includes_optional_fields_when_present(self, tmp_path):
        """error_code, duration_ms, and context are written when non-None."""
        from des.adapters.driven.logging.jsonl_nwave_log_writer import (
            JsonlNWaveLogWriter,
        )

        log_dir = tmp_path / "logs"
        writer = JsonlNWaveLogWriter(log_dir=log_dir)

        writer.log(
            _make_entry(
                error_code="E001",
                duration_ms=42.5,
                context={"agent": "crafter"},
            )
        )

        entries = _read_jsonl_lines(log_dir)
        assert entries[0]["error_code"] == "E001"
        assert entries[0]["duration_ms"] == 42.5
        assert entries[0]["context"] == {"agent": "crafter"}

    def test_excludes_none_optional_fields(self, tmp_path):
        """error_code and duration_ms are omitted when None."""
        from des.adapters.driven.logging.jsonl_nwave_log_writer import (
            JsonlNWaveLogWriter,
        )

        log_dir = tmp_path / "logs"
        writer = JsonlNWaveLogWriter(log_dir=log_dir)

        writer.log(_make_entry(error_code=None, duration_ms=None))

        entries = _read_jsonl_lines(log_dir)
        assert "error_code" not in entries[0]
        assert "duration_ms" not in entries[0]


class TestJsonlNWaveLogWriterAutoCreatesDirectory:
    """AC2: Auto-creates log directory if missing."""

    def test_creates_nested_log_directory_on_first_write(self, tmp_path):
        """Log directory is created automatically including parent dirs."""
        from des.adapters.driven.logging.jsonl_nwave_log_writer import (
            JsonlNWaveLogWriter,
        )

        log_dir = tmp_path / "deep" / "nested" / "logs"
        assert not log_dir.exists()

        writer = JsonlNWaveLogWriter(log_dir=log_dir)
        writer.log(_make_entry())

        assert log_dir.exists()
        assert len(_read_jsonl_lines(log_dir)) == 1


class TestJsonlNWaveLogWriterLevelFiltering:
    """AC3: Entries below set level are discarded."""

    @pytest.mark.parametrize(
        "min_level,entry_level,should_write",
        [
            (LogLevel.INFO, LogLevel.DEBUG, False),
            (LogLevel.INFO, LogLevel.INFO, True),
            (LogLevel.INFO, LogLevel.WARN, True),
            (LogLevel.WARN, LogLevel.INFO, False),
            (LogLevel.WARN, LogLevel.WARN, True),
            (LogLevel.ERROR, LogLevel.WARN, False),
            (LogLevel.ERROR, LogLevel.ERROR, True),
        ],
    )
    def test_filters_entries_by_minimum_level(
        self, tmp_path, min_level, entry_level, should_write
    ):
        """Entries below minimum level are discarded; at or above are written."""
        from des.adapters.driven.logging.jsonl_nwave_log_writer import (
            JsonlNWaveLogWriter,
        )

        log_dir = tmp_path / "logs"
        writer = JsonlNWaveLogWriter(log_dir=log_dir)
        writer.set_level(min_level)

        writer.log(_make_entry(level=entry_level))

        entries = _read_jsonl_lines(log_dir)
        if should_write:
            assert len(entries) == 1
        else:
            assert len(entries) == 0


class TestJsonlNWaveLogWriterNeverRaises:
    """AC4: Never raises exceptions (logging must not break operations)."""

    def test_swallows_exception_on_write_failure(self, tmp_path):
        """Write to a read-only directory does not raise."""
        from des.adapters.driven.logging.jsonl_nwave_log_writer import (
            JsonlNWaveLogWriter,
        )

        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)
        writer = JsonlNWaveLogWriter(log_dir=log_dir)

        # Make directory read-only to force write failure
        log_dir.chmod(0o444)

        try:
            # Must not raise
            writer.log(_make_entry())
        finally:
            # Restore permissions for cleanup
            log_dir.chmod(0o755)


# ---------------------------------------------------------------------------
# NullNWaveLogWriter Tests
# ---------------------------------------------------------------------------


class TestNullNWaveLogWriterIsNoOp:
    """AC5: NullNWaveLogWriter.log() is a no-op."""

    def test_implements_nwave_log_writer_interface(self):
        """NullNWaveLogWriter is an instance of NWaveLogWriter port."""
        from des.adapters.driven.logging.null_nwave_log_writer import (
            NullNWaveLogWriter,
        )

        writer = NullNWaveLogWriter()

        assert isinstance(writer, NWaveLogWriter)

    def test_log_and_set_level_accept_calls_without_side_effects(self):
        """NullNWaveLogWriter.log() and set_level() return None with no side effects."""
        from des.adapters.driven.logging.null_nwave_log_writer import (
            NullNWaveLogWriter,
        )

        writer = NullNWaveLogWriter()

        assert writer.log(_make_entry()) is None
        assert writer.set_level(LogLevel.ERROR) is None
