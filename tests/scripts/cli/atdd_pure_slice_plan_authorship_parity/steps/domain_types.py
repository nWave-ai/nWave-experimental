"""Domain types for the slice-plan-authorship-parity acceptance slice.

`docs/feature/parallel-by-default-distill-slicing/feature-delta.md` D-1..D-6 /
slice-01 (Mandate-12 criterion 1). Every domain noun used in the Gherkin is
expressed once here as a typed enum or NewType. Step bodies and the
composition service consume these typed parameters -- no raw ``str`` where a
domain enum exists.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "parallel-by-default-distill-slicing").
FeatureId = NewType("FeatureId", str)


class DependencyVerdict(str, Enum):
    """User-observable verdict of one validate-feature-delta CLI invocation.

    Slice-01's own claim (D-2) is that under `--require-slice-plan
    --format=json` a DISTILL-originated fixture and a DISCUSS-originated one
    with equivalent Slice Plan cell content NEVER produce a different token
    -- so this AT set only ever expects to observe `accepted` or
    `unjustified-slice-dependency` (the two verdicts the three tried
    combinations can produce). Any other token is an off-contract surprise
    the gate must fail loudly on, not silently swallow -- see
    `ValidationResult.verdict`.
    """

    ACCEPTED = "accepted"
    UNJUSTIFIED_SLICE_DEPENDENCY = "unjustified_slice_dependency"
    UNRECOGNISED_INVOCATION = "unrecognised_invocation"


class SecondRowShape(str, Enum):
    """The shape of the ONE row under test -- the plan's second data row.

    Every fixture (both the DISCUSS-shaped and the DISTILL-shaped one) carries
    a fixed `@walking_skeleton`-annotated first row (keeps the pre-existing
    cohesion-MECC floor from vetoing a plan whose only row happens to be
    `@infrastructure`) plus this second, varying row -- mirrors the sibling
    parallel-by-default-slice-plan slice-01 fixture shape verbatim.

    NO_ANNOTATION          -- empty Annotation, empty Justification
                               (Domain Example 1 -- the flipped default).
    DEPENDENCY_JUSTIFIED   -- `depends-on slice-01`, non-empty Justification
                               (Domain Example 2).
    DEPENDENCY_UNJUSTIFIED -- `depends-on slice-01`, empty Justification
                               (Domain Example 3 -- the rejection).
    """

    NO_ANNOTATION = "no_annotation"
    DEPENDENCY_JUSTIFIED = "dependency_justified"
    DEPENDENCY_UNJUSTIFIED = "dependency_unjustified"


# Gherkin-phrase -> typed-value lookup. Keeps each step body a single typed
# lookup + a single composition call (Mandate-12 criterion 3: no control flow
# in step bodies).
SECOND_ROW_SHAPE_BY_PHRASE: dict[str, SecondRowShape] = {
    "no annotation and an empty Justification": SecondRowShape.NO_ANNOTATION,
    "depends-on slice-01 with a non-empty Justification": (
        SecondRowShape.DEPENDENCY_JUSTIFIED
    ),
    "depends-on slice-01 with an empty Justification": (
        SecondRowShape.DEPENDENCY_UNJUSTIFIED
    ),
}

VERDICT_BY_PHRASE: dict[str, DependencyVerdict] = {
    "accepted": DependencyVerdict.ACCEPTED,
    "rejected for an unjustified slice dependency": (
        DependencyVerdict.UNJUSTIFIED_SLICE_DEPENDENCY
    ),
}
