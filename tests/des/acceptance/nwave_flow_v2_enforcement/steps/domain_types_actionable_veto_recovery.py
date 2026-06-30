"""Typed domain vocabulary for the fix-actionable-veto-recovery slice-01 ATs.

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the slice-01
Gherkin names is expressed once here as a typed enum, so the composition method
consumes a typed parameter (no raw ``str`` where an enum exists). The slice has
ONE scenario shape (a bare veto must now carry an actionable recovery hint)
ranging over the 6 enumerated bare-veto SITES -- so the DSL emerges from a single
``VetoSite`` enum, not from decorator proliferation.

These types are TEST-LOCAL (they never import production code) -- the ATs drive
the SUT only through composition-root driving ports (Mandate-13).
"""

from __future__ import annotations

from enum import Enum


class GateDecision(Enum):
    """The observable spine hook decision surface (allow vs block)."""

    ALLOW = "allow"
    BLOCK = "block"


class VetoSite(Enum):
    """The 6 enumerated bare-veto sites the fix makes self-documenting.

    Each value is the discriminating error-code / symbol the veto's ``reason``
    carries at HEAD (the SEAM the AT names, NOT a line number -- the AT drives on
    the error-code). The composition root arms the precondition state that steers
    the REAL production service down each veto's branch, then reads the resulting
    ``HookDecision.recovery_suggestions``.
    """

    WAVE_ACTIVE_INDETERMINATE = "WAVE_ACTIVE_INDETERMINATE"
    CLASSIC_PROMPT_INVALID = "CLASSIC_PROMPT_INVALID"
    ATDD_PURE_DISPATCH_DEFECTIVE = "ATDD_PURE_DISPATCH_DEFECTIVE"
    ATDD_PURE_PROMPT_INVALID = "ATDD_PURE_PROMPT_INVALID"
    DISCUSS_GATE_IN = "DISCUSS_GATE_IN"
    DISCUSS_GATE_OUT = "DISCUSS_GATE_OUT"
