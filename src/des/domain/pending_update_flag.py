"""PendingUpdateFlag domain dataclass.

Represents a deferred nWave update request persisted at
``~/.nwave/pending-update.json`` and replayed by the SessionStart early-phase
handler. Pure domain: no I/O, no subprocess. Immutable — use
``dataclasses.replace()`` to produce updated copies.

Attempt cap invariant (N=3): once ``attempt_count >= 3`` the flag reports
``attempt_cap_reached()`` as True and the application layer must refuse further
apply() calls and surface the stored ``last_error``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


_ATTEMPT_CAP = 3
_VALID_PM: frozenset[str] = frozenset({"pipx", "uv", "unknown"})


@dataclass(frozen=True)
class PendingUpdateFlag:
    """Immutable record of a deferred nWave self-update request."""

    pm: Literal["pipx", "uv", "unknown"]
    pm_binary_abspath: str
    target_version: str
    requested_at: str
    attempt_count: int = 0
    last_error: str | None = None

    def attempt_cap_reached(self) -> bool:
        """Return True when the attempt cap (N=3) has been reached or exceeded."""
        return self.attempt_count >= _ATTEMPT_CAP

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict for persistence."""
        return {
            "pm": self.pm,
            "pm_binary_abspath": self.pm_binary_abspath,
            "target_version": self.target_version,
            "requested_at": self.requested_at,
            "attempt_count": self.attempt_count,
            "last_error": self.last_error,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> PendingUpdateFlag:
        """Rehydrate from a persisted dict, validating the pm literal.

        Raises:
            ValueError: if ``pm`` is not one of ``pipx``, ``uv``, ``unknown``.
        """
        pm = payload["pm"]
        if pm not in _VALID_PM:
            raise ValueError(f"pm must be one of {sorted(_VALID_PM)}, got {pm!r}")
        return cls(
            pm=pm,
            pm_binary_abspath=payload["pm_binary_abspath"],
            target_version=payload["target_version"],
            requested_at=payload["requested_at"],
            attempt_count=payload.get("attempt_count", 0),
            last_error=payload.get("last_error"),
        )
