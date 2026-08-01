"""Domain types for the unified-event-store slice-04 cross-domain-timeline AT.

SSOT-via-types (Mandate-12 criterion 1): the observable captured from
driving the CLI's default cross-domain mode is one typed value object, so
step bodies stay typed lookups + a composition call (criterion 3), never
inline control-flow.

This module imports NO not-yet-created production name -- pure value-object
declaration, collection-safe at HEAD regardless of `CrossDomainReader`'s
scaffold state. Shape mirrors `QueryObservable` (slice-03,
`query_domain_types.py`) deliberately -- both observe the SAME CLI module
now, `des.cli.event_store_query`, just its two different modes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CrossDomainObservable:
    """The observable captured from driving `des event-store-query`'s
    default (no `--family`) cross-domain mode in-process, once.

    `records`/`measured_count`/`could_not_verify_count`/
    `could_not_verify_reasons` stay `None` until the emitted JSON payload is
    parsed -- which never happens while `CrossDomainReader.read_across()` is
    a RED-at-HEAD scaffold, because its `AssertionError` is raised (and
    caught by the composition into `scaffold_error`) BEFORE `main()` ever
    reaches its `_emit()` call. A `Then` step asserting e.g. `records is not
    None` therefore fails with a clear message naming what never happened,
    rather than a bare `NoneType`/JSON-parse error.

    `unhandled_exception` is DISTINCT from `scaffold_error` (mirrors
    `QueryObservable`): it carries any NON-`AssertionError` exception
    `main()` let escape -- a real production bug, never the intentional
    `__SCAFFOLD__` marker.
    """

    exit_code: int | None
    captured_output: str
    records: list[dict[str, object]] | None = None
    measured_count: int | None = None
    could_not_verify_count: int | None = None
    could_not_verify_reasons: list[str] | None = None
    scaffold_error: str | None = None
    unhandled_exception: str | None = None


__all__ = ["CrossDomainObservable"]
