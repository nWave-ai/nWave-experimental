"""Domain types for the at-in-process-port-default slice-03 enforcement levers.

SSOT-via-types (Mandate-12 criterion 1): the closed observables each lever pins
are typed value objects, so the step bodies are typed lookups + a composition
call (criterion 3) and carry no inline logic.

This module imports NO not-yet-created production name -- it is pure value-object
declaration, collection-safe at HEAD (DESIGN P1). The levers' production seams
(the new readiness invariants, the widened spawn-lint, the per-language
spawn-detector, the F821 re-wire, the coverage check, the ZOMBIES-zero floor) are
all reached at RUNTIME inside the in-process gate call, never imported here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class GateVerdict(str, Enum):
    """The observable a readiness/carpaccio gate emits (port-exposed)."""

    CLEARED = "cleared"
    REFUSED = "refused"
    # Target-aware NOT_APPLICABLE: a lever that cannot apply to this target
    # (e.g. the Python-only F821 lever on a Rust/Go project) clears WITHOUT a
    # false flag, and says so loudly. Never a silent pass, never a false refuse.
    NOT_APPLICABLE = "not-applicable"
    # Degrade-LOUD: the lever could not run (unparseable file, CodeFactPort chain
    # exhausted). INDETERMINATE is surfaced, never collapsed to cleared/refused.
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True)
class LeverObservable:
    """The observable captured from driving a gate entry IN-PROCESS for one lever.

    Every field is a port-exposed observable a ``Then`` asserts on -- the
    structured event the gate emits on its captured terminal output, never an
    internal struct field.

    * ``flagged`` -- True iff the gate FLAGGED the lever's violation (the spawn,
      the unwired entry, the missing-coverage, the missing sad-path).
    * ``flagged_target`` -- the symbol/file/AT the gate named in the flag (for the
      Then to assert the RIGHT thing was flagged, not a coincidental other one).
    * ``structured_event`` -- the event token the gate emitted (the machine-
      readable flag, e.g. ``"NonWalkingSkeletonSpawnFlagged"``); the gate FLAGS
      with a structured event, never a bare exit code (Q3 resolution).
    * ``confidence`` -- the CodeFactPort confidence label carried with a wiring
      flag (``binding-resolved`` / ``approx`` gate; ``noisy`` advise) -- the
      degrade-LOUD signal (DESIGN R6).
    * ``not_applicable_reason`` -- the loud reason a lever cleared as N/A on a
      non-applicable target (the health event the gate emitted).
    * ``forked_interpreter`` -- True iff the AT drove the gate by forking an
      interpreter. The slice-03 levers drive ``main(argv)`` in-process, so this is
      structurally False (this composition imports no ``subprocess``) -- pinning
      the in-process-default contract this very feature enforces.
    """

    flagged: bool
    structured_event: str
    flagged_target: str = ""
    confidence: str = ""
    not_applicable_reason: str = ""
    forked_interpreter: bool = False
    verdict: GateVerdict = GateVerdict.CLEARED
    captured_output: str = ""
    exit_code: int = 0
    extra: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class SpawnDetectorOutcome:
    """The per-language spawn-detector observable (lever-5 / fixture-scale-a).

    The detector is PER-LANGUAGE, AST/CodeFactPort-based, git-free, and
    degrade-LOUD when the language is unrecognized. The observable a ``Then``
    asserts on:

    * ``language`` -- the language the detector classified the fixture as.
    * ``spawn_flagged`` -- True iff an interpreter/process spawn was detected in a
      NON-``@walking_skeleton`` test (Python ``subprocess``/``sys.executable``,
      Rust ``Command::new``, Go ``exec.Command``).
    * ``walking_skeleton_exempt`` -- True iff a spawn was found but the bound
      ``.feature`` carries ``@walking_skeleton`` (legitimate e2e -> NOT flagged).
    * ``verdict`` -- ``NOT_APPLICABLE`` when the language is unrecognized
      (degrade-LOUD, never a false flag, never a silent pass).
    * ``git_invoked`` -- True iff the detector shelled out to ``git`` (it must
      NOT -- generality / target-machine agnosticism). Structurally False.
    """

    language: str
    spawn_flagged: bool
    walking_skeleton_exempt: bool = False
    verdict: GateVerdict = GateVerdict.CLEARED
    not_applicable_reason: str = ""
    git_invoked: bool = False
    captured_output: str = ""
