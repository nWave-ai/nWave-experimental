"""Typed domain vocabulary for the f-design-devops-review-gate slice-03 ATs.

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the Gherkin
names is expressed once as a typed enum, so each composition method consumes a
typed parameter (no raw ``str`` where an enum exists). The DSL emerges from these
enums, not from decorator proliferation.

slice-03 REUSES the slice-01 vocabulary VERBATIM for the boundary noun --
``WaveBoundary`` is imported from ``domain_types`` (the SSOT-not-duplication proof
extends to the test types too: the SAME enum ranges over the DISTILL wave).
slice-03 ADDS only the one noun slice-01/02 did not need: the lifecycle-event the
flavor dispatcher resolves the DELIVER-entry carpaccio backstop stack from
(AT-11).

These types are TEST-LOCAL (they never import production code for business logic)
-- the ATs drive the SUT only through the composition-root resolution seam (the
REAL spine ``resolve_stack`` over the shipped registry + the REAL flavor parser
over the shipped flavor file), Mandate-13 driving-port-only.
"""

from __future__ import annotations

from enum import Enum

# Re-export the slice-01 boundary vocabulary VERBATIM (SSOT, no duplication): the
# SAME gate-out boundary noun ranges over the DISTILL wave.
from .domain_types import WaveBoundary


__all__ = [
    "DispatchLifecycle",
    "WaveBoundary",
]


class DispatchLifecycle(Enum):
    """The lifecycle-event the flavor dispatcher resolves a gate composition for.

    The atdd_pure flavor declares its DELIVER-entry carpaccio stack under
    ``lifecycle_events`` (nWave/flavors/atdd_pure.yaml). The live
    ``carpaccio_intercept.evaluate_atdd_pure_dispatch`` iterates the
    ``dispatch.pre`` composition on every DELIVER Agent/Task dispatch -- the
    surface AT-11's backstop placement rides.

    * ``DISPATCH_PRE`` -- the pre-dispatch carpaccio stack (the DELIVER-entry
      backstop, CT-9 / DDD-5): an incomplete slice cannot enter DELIVER even if
      the DISTILL gate-out was bypassed.
    """

    DISPATCH_PRE = "dispatch.pre"
