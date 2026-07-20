"""Domain types for the parallel-safety-report / Feature-Plan-input acceptance
slice (slice-02).

`docs/feature/parallel-by-default-feature-plan/feature-delta.md` D-6/D-7 /
slice-02 (Mandate-12 criterion 1). Every domain noun used in the Gherkin is
expressed once here as a typed enum. Step bodies and the composition service
consume these typed parameters -- no raw ``str`` where a domain enum exists.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


EpicId = NewType("EpicId", str)
FeatureId = NewType("FeatureId", str)


class MeasurementFixture(str, Enum):
    """Which real-repo fixture backs the measurement -- selects the tracked
    files + the `--scope` path bindings for `feature-a`/`feature-b`
    (Domain Examples 4-6).

    DISJOINT   -- feature-a and feature-b touch separate files -> MEASURED-SAFE.
    OVERLAPPING -- both touch one shared file -> DRIFT, naming it.
    TIMED_OUT  -- feature-a's file cannot be measured within budget -> UNMEASURED.
    """

    DISJOINT = "disjoint"
    OVERLAPPING = "overlapping"
    TIMED_OUT = "timed_out"


class ReportOutcome(str, Enum):
    """The closed verdict-or-rejection token this composition can observe.

    Superset of the report's `ParallelSafetyReport.verdict` closed set
    (MEASURED-SAFE/DRIFT/UNMEASURED) plus the distinct
    `ParallelSafetyInputRejected` event, mapped onto one enum so a Then-step
    reads a single typed value regardless of which JSON event fired. An
    off-contract or absent token raises rather than silently defaulting (see
    `ReportResult.outcome`) -- a crafter that widens the set, or misspells a
    token, fails loudly.
    """

    MEASURED_SAFE = "measured_safe"
    DRIFT = "drift"
    UNMEASURED = "unmeasured"
    INPUT_REJECTED = "input_rejected"
    UNRECOGNISED_INVOCATION = "unrecognised_invocation"


class InputSourceCase(str, Enum):
    """CT-8: the two ways an invocation's input source can be malformed."""

    BOTH_SUPPLIED = "both_supplied"
    NEITHER_SUPPLIED = "neither_supplied"


# Gherkin-phrase -> typed-value lookups. Module-level dicts keep each step
# body a single typed lookup + a single composition call (Mandate-12
# criterion 3: no control flow in step bodies).

OUTCOME_BY_PHRASE: dict[str, ReportOutcome] = {
    "MEASURED-SAFE": ReportOutcome.MEASURED_SAFE,
    "DRIFT naming the overlapping file": ReportOutcome.DRIFT,
    "UNMEASURED naming the unmeasurable file": ReportOutcome.UNMEASURED,
}

INPUT_SOURCE_CASE_BY_PHRASE: dict[str, InputSourceCase] = {
    "both --epic-delta and --feature-delta supplied": InputSourceCase.BOTH_SUPPLIED,
    "neither --epic-delta nor --feature-delta supplied": (
        InputSourceCase.NEITHER_SUPPLIED
    ),
}
