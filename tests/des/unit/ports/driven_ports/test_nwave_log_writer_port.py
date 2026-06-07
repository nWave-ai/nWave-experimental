"""Unit tests for NWaveLogWriter port, NWaveLogEntry dataclass, and LogLevel enum.

Tests verify through the port interface (driven port boundary):
- AC1: NWaveLogWriter port defines log(entry) and set_level(level) methods
- AC2: NWaveLogEntry is a frozen dataclass with 9 fields
- AC3: LogLevel is an IntEnum with 4 levels: DEBUG=10, INFO=20, WARN=30, ERROR=40

Test Budget: 4 behaviors x 2 = 8 max unit tests.
"""

from dataclasses import FrozenInstanceError, asdict

import pytest

from des.ports.driven_ports.nwave_log_writer import (
    LogLevel,
    NWaveLogEntry,
    NWaveLogWriter,
)


# --- AC2: NWaveLogEntry dataclass ---


def test_nwave_log_entry_has_all_required_fields():
    """AC2: NWaveLogEntry has 9 fields with correct types."""
    entry = NWaveLogEntry(
        timestamp="2026-03-15T18:00:00Z",
        level=LogLevel.INFO,
        stage="hook",
        operation="pre_tool_use",
        event="entry",
        message="Processing hook invocation",
        operation_id="550e8400-e29b-41d4-a716-446655440000",
        error_code=None,
        duration_ms=None,
        context={},
    )

    assert entry.timestamp == "2026-03-15T18:00:00Z"
    assert entry.level == LogLevel.INFO
    assert entry.stage == "hook"
    assert entry.operation == "pre_tool_use"
    assert entry.event == "entry"
    assert entry.message == "Processing hook invocation"
    assert entry.operation_id == "550e8400-e29b-41d4-a716-446655440000"
    assert entry.error_code is None
    assert entry.duration_ms is None
    assert entry.context == {}


def test_nwave_log_entry_optional_fields_default_to_none():
    """AC2: error_code and duration_ms default to None, context defaults to empty dict."""
    entry = NWaveLogEntry(
        timestamp="2026-03-15T18:00:00Z",
        level=LogLevel.DEBUG,
        stage="install",
        operation="plugin_install",
        event="entry",
        message="Starting plugin installation",
        operation_id="550e8400-e29b-41d4-a716-446655440001",
    )

    assert entry.error_code is None
    assert entry.duration_ms is None
    assert entry.context == {}


def test_nwave_log_entry_is_frozen():
    """AC2: NWaveLogEntry is immutable (frozen dataclass)."""
    entry = NWaveLogEntry(
        timestamp="2026-03-15T18:00:00Z",
        level=LogLevel.INFO,
        stage="hook",
        operation="test",
        event="entry",
        message="test message",
        operation_id="550e8400-e29b-41d4-a716-446655440002",
    )

    with pytest.raises(FrozenInstanceError):
        entry.message = "modified"


def test_nwave_log_entry_serializes_to_dict():
    """AC2: NWaveLogEntry can be serialized to dict for downstream adapters."""
    entry = NWaveLogEntry(
        timestamp="2026-03-15T18:00:00Z",
        level=LogLevel.WARN,
        stage="runtime",
        operation="phase_validation",
        event="error",
        message="Phase validation failed",
        operation_id="550e8400-e29b-41d4-a716-446655440003",
        error_code="PHASE_INVALID",
        duration_ms=42.5,
        context={"step_id": "01-01"},
    )

    entry_dict = asdict(entry)

    assert entry_dict["timestamp"] == "2026-03-15T18:00:00Z"
    assert entry_dict["level"] == LogLevel.WARN
    assert entry_dict["stage"] == "runtime"
    assert entry_dict["error_code"] == "PHASE_INVALID"
    assert entry_dict["duration_ms"] == 42.5
    assert entry_dict["context"] == {"step_id": "01-01"}


# --- AC3: LogLevel enum ---


@pytest.mark.parametrize(
    "level,expected_value",
    [
        (LogLevel.DEBUG, 10),
        (LogLevel.INFO, 20),
        (LogLevel.WARN, 30),
        (LogLevel.ERROR, 40),
    ],
)
def test_log_level_has_correct_integer_values(level, expected_value):
    """AC3: LogLevel is an IntEnum with DEBUG=10, INFO=20, WARN=30, ERROR=40."""
    assert level == expected_value
    assert isinstance(level, int)


def test_log_level_supports_ordering():
    """AC3: LogLevel supports comparison for level filtering."""
    assert LogLevel.DEBUG < LogLevel.INFO < LogLevel.WARN < LogLevel.ERROR


# --- AC1: NWaveLogWriter port ---


def test_nwave_log_writer_defines_log_and_set_level_methods():
    """AC1: NWaveLogWriter defines log(entry) and set_level(level) as abstract methods."""

    class TestLogWriter(NWaveLogWriter):
        def __init__(self):
            self.entries = []
            self.current_level = LogLevel.INFO

        def log(self, entry: NWaveLogEntry) -> None:
            self.entries.append(entry)

        def set_level(self, level: LogLevel) -> None:
            self.current_level = level

    writer = TestLogWriter()
    entry = NWaveLogEntry(
        timestamp="2026-03-15T18:00:00Z",
        level=LogLevel.INFO,
        stage="hook",
        operation="test",
        event="entry",
        message="test",
        operation_id="550e8400-e29b-41d4-a716-446655440004",
    )

    writer.log(entry)
    writer.set_level(LogLevel.DEBUG)

    assert len(writer.entries) == 1
    assert writer.entries[0] is entry
    assert writer.current_level == LogLevel.DEBUG


def test_nwave_log_writer_cannot_be_instantiated_without_implementing_abstract_methods():
    """AC1: NWaveLogWriter is abstract -- cannot instantiate directly."""
    with pytest.raises(TypeError):
        NWaveLogWriter()  # type: ignore[abstract]
