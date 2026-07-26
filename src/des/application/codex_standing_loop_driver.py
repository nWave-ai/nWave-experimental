"""Codex SessionStart opportunity for bounded continued work.

This boundary deliberately does not schedule background work.  Codex offers a
SessionStart opportunity; a request that is due becomes one capsule for that
session, while a future request remains untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path


class Clock(Protocol):
    """Supplies UTC-aware time to the opportunity boundary."""

    now: datetime


@dataclass(frozen=True)
class ContinuedWorkRequest:
    """One bounded piece of work that may become actionable in a session."""

    project_root: Path
    outcome: str
    due_at: datetime
    max_tokens: int
    max_wall_seconds: int


@dataclass(frozen=True)
class DueWorkCapsule:
    """The bounded instruction a host may inject into its current session."""

    outcome: str
    max_tokens: int
    max_wall_seconds: int


class CodexSessionStartLoopDriver:
    """Projects a due request into one SessionStart capsule, never a scheduler."""

    def __init__(self, *, clock: Clock) -> None:
        self._clock = clock

    def session_started(self, request: ContinuedWorkRequest) -> DueWorkCapsule | None:
        """Return a capsule only when the supplied opportunity is due."""
        if request.due_at > self._clock.now:
            return None
        return DueWorkCapsule(
            outcome=request.outcome,
            max_tokens=request.max_tokens,
            max_wall_seconds=request.max_wall_seconds,
        )
