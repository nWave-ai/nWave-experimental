"""SystemClock — real-time clock adapter for ClockPort."""

from __future__ import annotations

import time


class SystemClock:
    """
    Real-time clock adapter.

    probe(): tick twice (time.monotonic), assert t2 >= t1.
    Catches hardware/VM clock regression at startup (DD-A5).
    """

    def now(self) -> float:
        """Return current time as a Unix timestamp (float seconds)."""
        return time.time()

    def probe(self) -> None:
        """
        Startup health check — verify the clock is monotone.

        Calls now() twice and asserts t2 >= t1.  On regression, raises
        RuntimeError so the composition root can emit health.startup.refused
        and exit 70.

        Raises:
            RuntimeError: if the second reading precedes the first.
        """
        t1 = self.now()
        t2 = self.now()
        if t2 < t1:
            raise RuntimeError(
                f"SystemClock probe failed: clock went backwards "
                f"(t1={t1}, t2={t2}). Possible VM clock skew or NTP step."
            )
