"""nWave business vocabulary for the slice-01 two-layer authored AT structure.

DESIGN CORRECTION (2026-06-22b, DDD-1C..DDD-5C/8C/10C). The keystone is the
TWO-LAYER AUTHORED business-language acceptance-test structure (Gojko/GOOS canon),
NOT a generic config-parameterized engine. This module is the L1/L2 boundary's
typed domain vocabulary (Mandate-12): the business CONCEPT the L1 scenarios name
when they describe HOW the maintainer authored the feature-delta (the slice-plan
SHAPE), expressed once in the type system so the L2 driver and the step bodies share
one SSOT and step bodies carry no raw `str` where an enum exists.

NON-TAUTOLOGY DISCIPLINE (Sentinel fixture-theater blocker, 2026-06-22): the
correctness oracle is NOT a test-authored verdict string. `SlicePlanShape` describes
only the INPUT the test BUILDS (well-formed / no-plan / malformed / infra-only — a
fact known by construction of the fixture). The expected VERDICT for each shape is
the PRODUCTION constant the shipped gate assigns (imported from
`des.cli.validate_feature_delta`), and the closed Universe is the gate's PRODUCTION
verdict-token set — so the assertion reads the gate's own SSOT, never a test copy.
The observation comes from REAL parsed gate output (composition.py `_invoke_gate`),
so DELIVER cannot make the property green by returning a test constant by lookup.

There is NO generic framework here: no ExampleDomain / CommandStub / GenericFramework
/ vocabulary-config. The earlier generic-engine vocabulary (the indicted anti-pattern)
is replaced by this nWave business vocabulary (DDD-4C: the `generic_framework.py`
asset is REMOVED by DELIVER, not imported here).
"""

from __future__ import annotations

from enum import Enum

# The PRODUCTION verdict-token SSOT — imported (not copied) from the shipped gate.
# Importing a production CONSTANT for the assertion is reuse-first: it is the gate's
# own vocabulary, so an assertion against it is non-tautological (the observation is
# parsed from the real gate, the expectation is the gate's own published token).
from des.cli.validate_feature_delta import (
    VERDICT_ACCEPTED,
    VERDICT_MALFORMED_SLICE_PLAN,
    VERDICT_MALFORMED_WAVE_HEADING,
    VERDICT_MISSING_SLICE_PLAN,
    VERDICT_REJECTED_INFRA_ONLY,
)


class SlicePlanShape(str, Enum):
    """A recognised SHAPE the test BUILDS a maintainer's slice plan into.

    Each shape is a business-language description of how the test authors the
    feature-delta fixture — a fact KNOWN BY CONSTRUCTION (the test writes a
    well-formed / no-plan / malformed / infra-only section). It is the INPUT, not the
    expectation; the gate's verdict is OBSERVED from real output, never read from a
    test constant. The PBT property sweeps this finite input domain and asserts the
    REAL gate's verdict equals the gate's PRODUCTION verdict for that constructed shape.
    """

    WELL_FORMED = "well-formed"  # canonical heading + five columns + a value row
    NO_PLAN = "no-plan"  # the slice-plan section is absent
    MALFORMED = "malformed"  # the table header is not the canonical five columns
    INFRA_ONLY = (
        "infra-only"  # every slice row is annotated @infrastructure (value-less)
    )


#: The gate's CLOSED verdict Universe for --require-slice-plan, sourced from the
#: PRODUCTION constants (the gate's own SSOT). The property asserts every observed
#: verdict is drawn from THIS set — a contract-drift detector reading production, not
#: a test copy. All five slice-plan-mode tokens are included so an off-set verdict
#: (e.g. a feature-plan or reuse-analysis token leaking in) would falsify the property.
PRODUCTION_SLICE_PLAN_VERDICTS: frozenset[str] = frozenset(
    {
        VERDICT_ACCEPTED,
        VERDICT_MISSING_SLICE_PLAN,
        VERDICT_MALFORMED_SLICE_PLAN,
        VERDICT_MALFORMED_WAVE_HEADING,
        VERDICT_REJECTED_INFRA_ONLY,
    }
)


#: The correctness oracle: the PRODUCTION verdict the shipped gate assigns to each
#: constructed input shape. The KEY (shape) is the test-built input known by
#: construction; the VALUE is the gate's OWN production verdict constant, NOT a
#: test-authored string. The property asserts the REAL observed verdict equals this —
#: input built test-side, verdict observed from the real gate, expectation = the
#: gate's published token: non-tautological by construction (Sentinel fix).
PRODUCTION_VERDICT_FOR_SHAPE: dict[SlicePlanShape, str] = {
    SlicePlanShape.WELL_FORMED: VERDICT_ACCEPTED,
    SlicePlanShape.NO_PLAN: VERDICT_MISSING_SLICE_PLAN,
    SlicePlanShape.MALFORMED: VERDICT_MALFORMED_SLICE_PLAN,
    SlicePlanShape.INFRA_ONLY: VERDICT_REJECTED_INFRA_ONLY,
}


def shape_is_accepted(shape: SlicePlanShape) -> bool:
    """Whether a constructed slice-plan shape is accepted by the shipped gate.

    Derived from the PRODUCTION verdict constant for the shape (accepted iff the gate's
    own `VERDICT_ACCEPTED`). The property's accept-agrees invariant reads this so the
    accept/reject decision is anchored to the gate's published vocabulary, not a test
    boolean.
    """
    return PRODUCTION_VERDICT_FOR_SHAPE[shape] == VERDICT_ACCEPTED


__all__ = [
    "PRODUCTION_SLICE_PLAN_VERDICTS",
    "PRODUCTION_VERDICT_FOR_SHAPE",
    "SlicePlanShape",
    "shape_is_accepted",
]
