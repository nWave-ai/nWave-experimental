"""NullNWaveLogWriter - NullObject pattern for NWaveLogWriter port.

Used when observability logging is disabled (default).
Accepts all log() and set_level() calls without performing any I/O.
"""

from des.ports.driven_ports.nwave_log_writer import (
    LogLevel,
    NWaveLogEntry,
    NWaveLogWriter,
)


class NullNWaveLogWriter(NWaveLogWriter):
    """No-op implementation of NWaveLogWriter for disabled logging."""

    def log(self, entry: NWaveLogEntry) -> None:
        """Accept entry without writing. No-op."""

    def set_level(self, level: LogLevel) -> None:
        """Accept level without storing. No-op."""
