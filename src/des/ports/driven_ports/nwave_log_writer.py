"""NWaveLogWriter - driven port for unified nWave observability logging.

Abstract interface defining how the application layer writes structured log
entries to the observability system.

Defined by: Application layer logging requirements.
Implemented by: NullNWaveLogWriter (default, no-op), future adapters.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class LogLevel(IntEnum):
    """Log severity levels for nWave observability.

    Levels follow the standard 10-increment convention for extensibility.
    Supports comparison operators for level-based filtering.
    """

    DEBUG = 10
    INFO = 20
    WARN = 30
    ERROR = 40


@dataclass(frozen=True)
class NWaveLogEntry:
    """A single structured log entry for nWave observability.

    Frozen (immutable) to ensure log entries cannot be modified after creation.

    Attributes:
        timestamp: ISO 8601 timestamp string.
        level: Severity level of the log entry.
        stage: System stage producing the entry
            ("install"|"hook"|"build"|"plugin"|"runtime").
        operation: Specific operation being performed.
        event: Event type ("entry"|"outcome"|"error"|"debug").
        message: Human-readable log message.
        operation_id: UUID correlating related log entries.
        error_code: Machine-readable error code (None if no error).
        duration_ms: Operation duration in milliseconds (None if not timed).
        context: Additional structured data for the entry.
    """

    timestamp: str
    level: LogLevel
    stage: str
    operation: str
    event: str
    message: str
    operation_id: str
    error_code: str | None = None
    duration_ms: float | None = None
    context: dict[str, Any] = field(default_factory=dict)


class NWaveLogWriter(ABC):
    """Driven port: writes structured log entries to the observability system.

    Adapters implement this port to direct log output to different
    destinations (null/no-op, stderr, file, etc.).
    """

    @abstractmethod
    def log(self, entry: NWaveLogEntry) -> None:
        """Write a single log entry.

        Args:
            entry: The structured log entry to write.
        """
        ...

    @abstractmethod
    def set_level(self, level: LogLevel) -> None:
        """Set the minimum log level for filtering.

        Entries below this level should be discarded by the adapter.

        Args:
            level: The minimum severity level to log.
        """
        ...
