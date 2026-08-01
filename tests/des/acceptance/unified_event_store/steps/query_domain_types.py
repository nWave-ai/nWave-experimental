"""Domain types for the unified-event-store slice-03 acceptance ATs
(`des event-store-query --family` single-family mode).

SSOT-via-types (Mandate-12 criterion 1): the observable captured from
driving the query CLI is a typed value object, so step bodies are typed
lookups + a composition call (criterion 3), never inline control-flow.

This module imports NO not-yet-created production name -- pure value-object
declaration, collection-safe at HEAD.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QueryObservable:
    """The observable captured from driving `event_store_query.main` once.

    `exit_code` is `None` when the call never returned (the RED-at-HEAD
    scaffold raised an uncaught `AssertionError` before `main()` could
    return one) -- a `Then` step asserting on the merged JSON payload fails
    with a clear message naming what never happened, rather than a bare
    `NoneType`/empty-string parse error. `scaffold_error` carries the caught
    scaffold message for diagnostics.

    `unhandled_exception` is DISTINCT from `scaffold_error`: it carries any
    NON-`AssertionError` exception `main()` let escape (e.g. a malformed
    ledger line raising `json.JSONDecodeError`, or a non-dict row raising
    `TypeError` deeper in the read path) -- a REAL production bug, not the
    intentional `__SCAFFOLD__` marker. The composition catches it so a
    `Then` step can fail with a clean, business-meaningful assertion
    ("the query must not crash") instead of letting a bare traceback escape
    the test boundary uncontrolled.
    """

    exit_code: int | None
    captured_output: str
    scaffold_error: str | None = None
    unhandled_exception: str | None = None


__all__ = ["QueryObservable"]
