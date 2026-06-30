"""Typed domain vocabulary for the f-declarative-gate-composition ATs.

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the Gherkin
names is expressed once here as a typed enum / dataclass, so each composition
method consumes a typed parameter (no raw ``str`` where an enum exists). The DSL
emerges from these enums, not from decorator proliferation -- one parametrized
scenario shape ranges over each enum's members.

These types are TEST-LOCAL (they never import production code) -- the ATs drive
the SUT only through composition-root driving ports (Mandate-13 driving-port-only).
"""

from __future__ import annotations

from enum import Enum


class WaveBoundary(Enum):
    """The two boundaries a wave's declared gate stack covers.

    ``gate-in`` is iterated on the wave-entering PreToolUse dispatch; ``gate-out``
    on the SubagentStop return. The flavor schema (OB-1 option a, ADR-DGC-001)
    declares ``wave_gate_stacks.<wave>.{gate-in,gate-out}`` -- the SAME ordered
    GateInvocation row schema the existing event compositions use.
    """

    GATE_IN = "gate-in"
    GATE_OUT = "gate-out"


class DiscussVetoSite(Enum):
    """The DISCUSS wave's two enumerated veto sites being lifted to declarative form.

    Each value is the discriminating error-code PREFIX the veto's ``reason`` carries
    (the SEAM the AT names, NOT a line number -- the AT drives on the error-code).
    The composition root arms the precondition that steers the REAL production
    service down each veto's branch via the declared ``wave_gate_stacks.discuss``
    composition, then reads the resulting ``HookDecision`` surface.

      * ``DISCUSS_GATE_IN``  -- PreToolUse gate-in, discuss-entering dispatch whose
        product-SSOT precondition is unmet.
      * ``DISCUSS_GATE_OUT`` -- SubagentStop gate-out, discuss return whose
        feature-delta slice plan is rejected (the structural cohesion veto, the
        first row of the declared 2-row gate-out list).
    """

    DISCUSS_GATE_IN = "DISCUSS_GATE_IN"
    DISCUSS_GATE_OUT = "DISCUSS_GATE_OUT"


class GateDecision(Enum):
    """The observable spine hook decision surface (allow vs block)."""

    ALLOW = "allow"
    BLOCK = "block"


# NOTE: a GateVerdict / OnFailure enum was deliberately NOT modeled here. The §17
# exit_code -> GateVerdict map lives in the production HANDLER (DESIGN [REF]
# Code-Design lines 748-752), NOT as a materialized result field -- so the ATs read
# the UnknownGate / INDETERMINATE class from the gate's JSON-stdout
# (GateInvocationResult.stdout) + the parsed GateInvocationResult.recovery_suggestions,
# never from a test-local verdict enum. Modeling a verdict enum here would invert
# crafter-matches-design (the test would invent a surface the DESIGN does not declare).
