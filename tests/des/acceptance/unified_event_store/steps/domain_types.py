"""Domain types for the unified-event-store slice-02 acceptance ATs.

SSOT-via-types (Mandate-12 criterion 1): the induced-fault vocabulary and the
observable captured from driving the probe are typed value objects, so step
bodies are typed lookups + a composition call (criterion 3), never inline
control-flow.

This module imports NO not-yet-created production name -- pure value-object
declaration, collection-safe at HEAD.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class InducedFault(str, Enum):
    """The three charter-declared filesystem faults (Scenario Outline text)."""

    MISSING_DIRECTORY = "is missing entirely"
    PERMISSION_DENIED = "denies permission"
    NOT_A_DIRECTORY = "is a file, not a directory"


@dataclass(frozen=True)
class ProbeObservable:
    """The observable captured from driving the probe CLI (subprocess or
    in-process).

    `exit_code` is `None` when the call never returned (the RED-at-HEAD
    scaffold raised an uncaught `AssertionError` before `main()` could
    return one) -- a `Then` step asserting `exit_code is not None` fails
    with a clear message naming what never happened, rather than a bare
    `NoneType` comparison error. `scaffold_error` carries that caught
    scaffold message for diagnostics.
    """

    exit_code: int | None
    captured_output: str
    scaffold_error: str | None = None


__all__ = ["InducedFault", "ProbeObservable"]
