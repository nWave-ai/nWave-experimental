"""Pytest config for the fix-slicecommitverified-emission slice-01 ATs.

slice-01 GREEN: the auto-backfill branch now exists -- `_carpaccio_order_block`
(carpaccio_intercept.py) attempts `_attempt_predecessor_backfill` (verify-then-
record against the predecessor commit) before blocking. The ADR-028 RED scaffold
xfail(strict) hook that marked the two backfill-driver scenarios is REMOVED at
GREEN, exactly as its lifecycle note prescribed (mirrors the
atdd_pure_spine_hardening conftest lifecycle): all three slice-01 scenarios now
pass GREEN --

  * AT-1 "auto-verified so the next slice enters" -- backfill->allow.
  * AT-2 "the auto-verification is real" -- the appended record names the
    predecessor (exactly one).
  * AT-3 "an already-verified predecessor is not verified again" -- the
    idempotent regression-pin (no duplicate record, still allow); it passed on
    master and keeps passing now that the backfill branch exists.
"""

from __future__ import annotations
