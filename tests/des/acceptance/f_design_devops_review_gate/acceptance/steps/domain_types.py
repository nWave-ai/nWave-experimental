"""Typed domain vocabulary for the f-design-devops-review-gate slice-01 ATs.

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the Gherkin
names is expressed once here as a typed enum, so each composition method consumes
a typed parameter (no raw ``str`` where an enum exists). The DSL emerges from these
enums, not from decorator proliferation -- one parametrized scenario shape ranges
over each enum's members.

These types are TEST-LOCAL (they never import production code) -- the ATs drive
the SUT only through the composition-root resolution seam + the REAL ``des`` CLI
subprocess (Mandate-13 driving-port-only).

Slice scope (brief §8 slice-01 walking-skeleton): the DESIGN review-verdict gate
end-to-end -- the registry->spine gate-stack resolution seam (AT-1) + the
record->verify CONSUMER veto loop driven through the real ``des`` CLI (AT-2..4).
"""

from __future__ import annotations

from enum import Enum


class ReviewerVerdict(Enum):
    """The two outcomes a wave reviewer records (O-4 both-outcomes, DDD-6).

    The producer CLI (``des record-design-review --verdict <v>``) writes BOTH --
    an un-written NEEDS_REVISION would collapse into INDETERMINATE alongside "no
    review yet", defeating the veto. Mirrors ``DiscussReviewToken`` for the DESIGN
    wave.

    * ``APPROVED`` -- the solution-architect-reviewer found no blocking objection
      (NOT an authorizing GO -- §22.0).
    * ``NEEDS_REVISION`` -- the reviewer VETO; the gate-out must mechanically honor it.
    """

    APPROVED = "approved"
    NEEDS_REVISION = "needs-revision"


class GateOutcome(Enum):
    """The observable verdict the DESIGN gate-out CONSUMER veto projects.

    The §17 GateVerdict tokens the ``ReviewVerdictGate`` core emits, observable on
    the ``des verify-design-review`` JSON-stdout + exit code (DDD-7, ADR-GV-001 --
    no sixth verdict). Slice-01 asserts three of the five:

    * ``PASS`` -- an artefact-current APPROVED verdict exists -> exit 0
      ("no objection found", NOT a GO).
    * ``VETOED`` -- the reviewer recorded NEEDS_REVISION -> exit 1 (a control veto).
    * ``INDETERMINATE`` -- no verdict recorded (absent) -> exit 1 (degrade-LOUD).
    """

    PASS = "pass"
    VETOED = "vetoed"
    INDETERMINATE = "indeterminate"


class WaveBoundary(Enum):
    """The boundary of a wave's declared gate stack the dispatcher resolves.

    The DESIGN gate is a gate-OUT concern (a wave's OUTPUT is reviewed on the
    wave-owner's RETURN, DDD-2). The canonical wave-contract registry
    (ADR-FLOW-006 D2) declares ``gate_stack.gate-out`` per wave -- the SAME ordered
    GateInvocation row schema the existing ``nWave/waves/discuss.yaml`` carries.
    """

    GATE_OUT = "gate-out"
