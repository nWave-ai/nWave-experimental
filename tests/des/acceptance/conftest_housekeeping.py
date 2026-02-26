"""Test fixtures for DES Housekeeping acceptance tests.

Provides a deterministic TimeProvider for controlling "now" in tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from des.ports.driven_ports.time_provider_port import TimeProvider


if TYPE_CHECKING:
    from datetime import datetime


class FixedTimeProvider(TimeProvider):
    """TimeProvider that returns a fixed datetime for deterministic testing."""

    def __init__(self, fixed_time: datetime) -> None:
        self._fixed_time = fixed_time

    def now_utc(self) -> datetime:
        return self._fixed_time
