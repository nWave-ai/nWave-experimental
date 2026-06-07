"""Update check policy domain rule.

Pure business rule for determining whether an update check should be performed.
No I/O dependencies. Evaluates frequency windows, skipped-version lists, and
first-run detection.

Follows the PolicyResult pattern: frozen dataclass result + stateless class.

Frequency windows:
    every_session: always CHECK (no window)
    daily:         window = 24 hours
    weekly:        window = 168 hours
    never:         always SKIP
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum


class CheckDecision(Enum):
    """Decision returned by UpdateCheckPolicy.

    CHECK:    The update check should be performed.
    SKIP:     The update check should be skipped.
    UP_TO_DATE: Used by the service layer (not by this policy).
    """

    CHECK = "CHECK"
    SKIP = "SKIP"
    UP_TO_DATE = "UP_TO_DATE"


class UpdateCheckPolicy:
    """Evaluates whether an update check should be performed.

    Business rules (in priority order):
    1. frequency=never  → always SKIP
    2. latest_version in skipped_versions → SKIP
    3. No config present (frequency=None, last_checked=None) → CHECK (first run)
    4. frequency=every_session → always CHECK
    5. last_checked within window → SKIP
    6. last_checked outside window → CHECK
    """

    WINDOW_HOURS: dict[str, int] = {
        "daily": 24,
        "weekly": 168,
    }

    def evaluate(
        self,
        *,
        frequency: str | None,
        last_checked: datetime | None,
        latest_version: str | None,
        skipped_versions: list[str],
        current_time: datetime,
    ) -> CheckDecision:
        """Evaluate whether an update check should be performed.

        Args:
            frequency: Configured check frequency ('every_session', 'daily',
                       'weekly', 'never'), or None when config is absent.
            last_checked: Timestamp of the last completed check, or None.
            latest_version: Latest known version string, or None.
            skipped_versions: List of version strings the user has chosen to skip.
            current_time: Current UTC datetime (injected for testability).

        Returns:
            CheckDecision.CHECK if an update check should run,
            CheckDecision.SKIP  if the check should be skipped.
        """
        # Rule 1: never frequency — always SKIP
        if frequency == "never":
            return CheckDecision.SKIP

        # Rule 2: latest version in skipped list — SKIP
        if latest_version is not None and latest_version in skipped_versions:
            return CheckDecision.SKIP

        # Rule 3: first run — no config present
        if frequency is None and last_checked is None:
            return CheckDecision.CHECK

        # Rule 4: every_session — always CHECK
        if frequency == "every_session":
            return CheckDecision.CHECK

        # Rules 5 & 6: windowed frequencies (daily / weekly)
        if last_checked is None:
            return CheckDecision.CHECK

        window_hours = self.WINDOW_HOURS.get(frequency or "", 0)
        elapsed_hours = _hours_since(last_checked, current_time)

        if elapsed_hours < window_hours:
            return CheckDecision.SKIP

        return CheckDecision.CHECK


def _hours_since(past: datetime, now: datetime) -> float:
    """Return the number of hours elapsed between past and now."""
    # Normalise both to UTC-aware before subtracting
    if past.tzinfo is None:
        past = past.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    delta = now - past
    return delta.total_seconds() / 3600
