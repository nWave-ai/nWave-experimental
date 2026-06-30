"""Domain types for the future-slice-scaffold collection-scope acceptance slice.

Feature: fix-carpaccio-future-slice-scaffold-blocks-commit (C3, cohort S).
Every domain noun used in the Gherkin is expressed once here as a typed enum or
NewType (Mandate-12 criterion 1). Step bodies and the composition service
consume these typed parameters -- no raw ``str`` where a domain enum exists.

The slice scopes the E2 feature-scoped contract gate (``run_contract_gate``,
the ``_mode_feature_scoped`` path) so its ``.feature`` scenario collection is
narrowed to the SHIPPED+ENTERING slice set, excluding a not-yet-entered
``@slice-{future}`` scaffold already authored on disk. The observable is the
gate's exit code, the collected-scenario set, and the future-slice file content
(no ``@skip`` token added by the fix).
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "demo-multislice").
FeatureId = NewType("FeatureId", str)

# A ``@slice-NN`` slice identifier (e.g. "slice-01").
SliceId = NewType("SliceId", str)


class GateOutcome(str, Enum):
    """The user-observable outcome of one feature-scoped E2 contract-gate run.

    PASSES   -- ``run_contract_gate --feature-id ... --entering-slice ...``
                returned exit 0: the gate cleared the shipped+entering scope
                without running the future-slice RED driver.
    REFUSES  -- the gate returned a non-zero exit: it ran a driver it should
                not have (the future-slice RED scaffold) or otherwise refused.
    """

    PASSES = "passes"
    REFUSES = "refuses"


class SliceShape(str, Enum):
    """Which slices a fixture feature tree carries on disk.

    NON_FINAL_WITH_FUTURE_RED -- slice-01 (entering, a real green AT) PLUS a
        slice-02 active-RED scaffold already authored on disk. Entering slice
        is slice-01; slice-02 is the not-yet-entered future slice.
    FINAL_SINGLE              -- a single shipped slice-01, which is also the
        entering (final) slice; no future slices. Preservation case.
    """

    NON_FINAL_WITH_FUTURE_RED = "non_final_with_future_red"
    FINAL_SINGLE = "final_single"


# Gherkin-phrase -> typed-value lookups. Keeping these as module-level dicts
# lets each step body stay a single typed lookup + a single composition call
# (Mandate-12 criterion 3: no control flow in step bodies).

GATE_OUTCOME_BY_PHRASE: dict[str, GateOutcome] = {
    "passes": GateOutcome.PASSES,
    "refuses the commit": GateOutcome.REFUSES,
}
