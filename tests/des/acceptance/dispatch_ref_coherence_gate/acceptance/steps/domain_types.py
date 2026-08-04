"""Typed domain vocabulary for the dispatch-ref-coherence-gate ATs.

Mandate-12 (SSOT + Zero Duplication via Types): the verdict the gate emits is
expressed once here as a typed enum, so composition methods consume a typed
parameter (no raw ``str`` for the verdict). Mirrors
``tests/des/acceptance/f-wave-contract-coherence/acceptance/steps/domain_types.py``'s
``CoherenceVerdict`` -- same §17 GateVerdict vocabulary, a distinct test-local type
because this feature drives a different gate subcommand.

Test-local only (never imports production code) -- the ATs drive the SUT solely
through the composition-root subprocess seam (Mandate-13 driving-port-only).
"""

from __future__ import annotations

from enum import Enum


class DispatchRefVerdict(Enum):
    """The §17 GateVerdict tokens the dispatch-ref coherence gate emits.

    ADR-GV-001's five existing verdicts -- this gate introduces no sixth. Slice-04
    asserts three of the five: PASS (valid pointer, zero restatement), FAIL (missing
    pointer / unresolvable mode-or-lane / inline restatement), INDETERMINATE (target
    skill file missing/unreadable -- degrade-LOUD, Invariant 2).
    """

    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"
