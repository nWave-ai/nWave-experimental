"""Domain types for the at-in-process-port-default slice-04 path-genericity ATs.

SSOT-via-types (Mandate-12 criterion 1): the closed observables the path-discovery
levers pin are typed value objects, so the step bodies are typed lookups + a
composition call (criterion 3) and carry no inline logic.

This module imports NO not-yet-created production name -- it is pure value-object
declaration, collection-safe at HEAD (DESIGN P1). The path-resolution seam (the
levers' RESOLVED source + tests roots, replacing the hardcoded ``_TESTS`` /
``_SRC_DES``) is reached at RUNTIME inside the in-process gate call, never imported
here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class LayoutResolution(str, Enum):
    """The observable verdict of the levers' target-layout discovery (port-exposed)."""

    # The target's source + tests roots were RESOLVED (from explicit args, pyproject
    # testpaths, or a .nwave config) and the levers scanned the RIGHT dirs.
    RESOLVED = "resolved"
    # Degrade-LOUD: the layout could NOT be resolved (no conventional dir, no config) ->
    # the levers report NOT_APPLICABLE / INDETERMINATE with a named reason, never a
    # false-PASS on a wrong/empty directory, never a crash.
    NOT_RESOLVABLE = "not-resolvable"


@dataclass(frozen=True)
class LayoutDiscoveryObservable:
    """The observable captured from driving the readiness levers against a target project.

    Every field is a port-exposed observable a ``Then`` asserts on -- the resolved
    roots the gate scanned + the degrade-LOUD reason it emitted, never an internal
    struct field.

    * ``resolution`` -- whether the target layout was RESOLVED or NOT_RESOLVABLE.
    * ``resolved_tests_root`` -- the tests directory the levers actually scanned for the
      target (its ``spec/``), so the Then asserts the RIGHT dir was scanned, not the
      host ``tests/``.
    * ``resolved_source_root`` -- the source directory the levers actually scanned (its
      ``lib/``), not the host ``src/des``.
    * ``scanned_host_layout`` -- True iff the levers fell back to scanning the HOST nWave
      ``tests/`` / ``src/des`` instead of the target's roots (the defect: hardcoded
      globals). The fix makes this structurally False.
    * ``not_resolvable_reason`` -- the loud, named reason the levers emitted when the
      layout could not be resolved (the degrade-LOUD health signal); empty on a false
      silent pass (the RED for the sad path).
    * ``crashed`` -- True iff driving the levers on an unresolvable layout raised an
      unhandled exception (a crash, not a verdict). Must be False (degrade-LOUD, never a
      crash on a non-nWave layout).
    * ``forked_interpreter`` -- True iff the AT drove the gate by forking an interpreter.
      These ATs drive ``main(argv)`` in-process, so this is structurally False (this
      composition imports no ``subprocess``) -- pinning the in-process-default contract.
    """

    resolution: LayoutResolution
    resolved_tests_root: str = ""
    resolved_source_root: str = ""
    scanned_host_layout: bool = False
    not_resolvable_reason: str = ""
    crashed: bool = False
    forked_interpreter: bool = False
    captured_output: str = ""
    exit_code: int = 0
    extra: dict[str, object] = field(default_factory=dict)
