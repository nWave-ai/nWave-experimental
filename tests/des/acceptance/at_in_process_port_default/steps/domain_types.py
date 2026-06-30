"""Domain types for the at-in-process-port-default slice-01 exemplar ATs.

SSOT-via-types (Mandate-12 criterion 1): the closed observable the exemplar pins
is expressed as a typed value object, not a raw dict/str, so the step bodies are
typed lookups + a composition call (criterion 3) and carry no inline logic.

This module imports NO not-yet-created production name (no OutputPort, no
CapturingOutput) — it is pure value-object declaration, collection-safe at HEAD.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InProcessExemplarObservable:
    """The observable captured from driving `main(argv)` IN-PROCESS (DESIGN §2).

    The exemplar drives the REAL `des.cli.run_contract_gate.main` entry directly
    (no interpreter fork) and captures terminal output + the returned exit code.
    The fields below are the port-exposed observables a `Then` asserts on:

    * ``route_recognised`` -- True iff the entry recognised the in-process
      exemplar route (i.e. did NOT reject ``--inprocess-exemplar`` as an unknown
      flag). At HEAD the route does not exist => False => the RED.
    * ``routed_verdict_emitted`` -- True iff the captured output carries the
      in-process-routed exemplar verdict line (the observable the OutputPort
      capture would record once DELIVER threads the port through the entry). At
      HEAD no such line is emitted => False => the RED.
    * ``forked_interpreter`` -- True iff the driving call spawned a child
      interpreter. The exemplar drives ``main(argv)`` directly, so this is
      structurally False; the assertion pins the no-fork contract (the whole
      point of the feature).
    * ``captured_output`` / ``exit_code`` -- the raw captured terminal text and
      the entry's return code, for diagnostics.
    """

    route_recognised: bool
    routed_verdict_emitted: bool
    forked_interpreter: bool
    captured_output: str
    exit_code: int
