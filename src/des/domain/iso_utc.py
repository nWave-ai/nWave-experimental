"""des.domain.iso_utc -- the ISO-8601 UTC round-trip idiom, centralized.

Every DES timestamp crosses ledgers/CLIs/hooks as an ISO-8601 string ending in
``Z``, but ``datetime.fromisoformat`` does not accept a trailing ``Z`` and
``datetime.isoformat()`` never emits one -- it emits ``+00:00``. This module
is the ONE place that ``Z``/``+00:00`` round-trip is spelled out; callers use
these two functions instead of open-coding the ``.replace(...)`` pair.
"""

from __future__ import annotations

from datetime import datetime


def parse_iso_utc(value: str) -> datetime:
    """Parse an ISO-8601 UTC timestamp, accepting a trailing ``Z``."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def format_iso_utc(value: datetime) -> str:
    """Format a datetime as ISO-8601 UTC with a trailing ``Z``."""
    return value.isoformat().replace("+00:00", "Z")
