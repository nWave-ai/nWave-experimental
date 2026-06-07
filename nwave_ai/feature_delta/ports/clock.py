"""ClockPort — driving port for time access."""

from __future__ import annotations

from typing import Protocol


class ClockPort(Protocol):
    def now(self) -> float: ...
    def probe(self) -> None: ...
