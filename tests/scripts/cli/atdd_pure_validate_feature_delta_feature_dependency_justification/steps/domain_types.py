"""Domain types for the feature-dependency-justification acceptance slice.

`docs/feature/parallel-by-default-feature-plan/feature-delta.md` D-1..D-7 /
slice-01 (Mandate-12 criterion 1). Every domain noun used in the Gherkin is
expressed once here as a typed enum or NewType. Step bodies and the
composition service consume these typed parameters -- no raw ``str`` where a
domain enum exists.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case epic or feature identifier (e.g. "swarm-parallel-delivery").
EpicId = NewType("EpicId", str)
FeatureId = NewType("FeatureId", str)


class CheckMode(str, Enum):
    """Which `validate-feature-delta` plan mode a scenario drives.

    FEATURE_PLAN -- ``--require-feature-plan --format=json`` against an
                    epic-delta's `[REF] Feature Plan` (this feature's own
                    surface).
    SLICE_PLAN   -- ``--require-slice-plan --format=json`` against a
                    feature-delta's `[REF] Slice Plan` -- driven ONLY by the
                    isolation scenario, which proves the new feature-grain
                    rule does not disturb the existing slice-grain rule
                    (D-6 / CT-4, mirrors row-1's own isolation scenario in
                    the opposite direction).
    """

    FEATURE_PLAN = "feature_plan"
    SLICE_PLAN = "slice_plan"


class DependencyVerdict(str, Enum):
    """User-observable verdict of one validate-feature-delta CLI invocation.

    Superset of both plan modes' closed token sets -- token strings never
    collide between modes, so one enum safely maps either. The feature-plan
    mode's SIX-token closed set this slice introduces (D-1/D-2/DA) is:
    ``accepted | missing-feature-plan | malformed-feature-plan |
    malformed-wave-heading | rejected-infra-only |
    unjustified-feature-dependency``; the slice-plan mode's six-token set
    (unchanged by this feature, D-6/CT-4) is:
    ``accepted | missing-slice-plan | malformed-slice-plan |
    malformed-wave-heading | rejected-infra-only |
    unjustified-slice-dependency``. An off-contract or absent token raises
    rather than silently defaulting (see ``ValidationResult.verdict``), so a
    crafter that widens either set, or phrases a diagnostic outside it, fails
    loudly -- never a silent misclassification.

    UNJUSTIFIED_FEATURE_DEPENDENCY -- token ``unjustified-feature-dependency``:
        THE new slice-01 verdict. A Feature Plan row's Annotation cell
        matches `depends-on {feature-id}` and its Justification cell is
        empty.
    UNRECOGNISED_INVOCATION -- NO structured ``verdict`` token in stdout: the
        CLI did not produce JSON output for this invocation (never expected
        on either mode's shipped flags; a genuine contract break if seen).
    """

    ACCEPTED = "accepted"
    MISSING_FEATURE_PLAN = "missing_feature_plan"
    MALFORMED_FEATURE_PLAN = "malformed_feature_plan"
    MALFORMED_WAVE_HEADING = "malformed_wave_heading"
    REJECTED_INFRA_ONLY = "rejected_infra_only"
    UNJUSTIFIED_FEATURE_DEPENDENCY = "unjustified_feature_dependency"
    MISSING_SLICE_PLAN = "missing_slice_plan"
    MALFORMED_SLICE_PLAN = "malformed_slice_plan"
    UNJUSTIFIED_SLICE_DEPENDENCY = "unjustified_slice_dependency"
    UNRECOGNISED_INVOCATION = "unrecognised_invocation"


class SecondRowShape(str, Enum):
    """The shape of the ONE row under test -- the plan's second data row.

    Every scenario's fixture carries a fixed `@walking_skeleton`-annotated
    first row (keeps the pre-existing cohesion-MECC floor from vetoing a
    plan whose only row happens to be `@infrastructure`) plus this
    second, varying row -- so each scenario isolates exactly one Annotation/
    Justification combination.

    NO_ANNOTATION            -- empty Annotation, empty Justification
                                (Domain Example 1 -- the flipped default).
    WALKING_SKELETON         -- `@walking_skeleton`, empty Justification.
    INFRASTRUCTURE           -- `@infrastructure`, empty Justification.
    DEPENDENCY_JUSTIFIED     -- `depends-on webhook-retry-core`, non-empty
                                Justification (Domain Example 2).
    DEPENDENCY_UNJUSTIFIED   -- `depends-on webhook-retry-core`, empty
                                Justification (Domain Example 3 -- the new
                                rejection).
    DEPENDENCY_MALFORMED_ROW -- `depends-on webhook-retry-core` Annotation,
                                but the row itself drops the Justification
                                column entirely (fewer than five cells) --
                                the "malformed token fails LOUD" guard (CT-5).
    """

    NO_ANNOTATION = "no_annotation"
    WALKING_SKELETON = "walking_skeleton"
    INFRASTRUCTURE = "infrastructure"
    DEPENDENCY_JUSTIFIED = "dependency_justified"
    DEPENDENCY_UNJUSTIFIED = "dependency_unjustified"
    DEPENDENCY_MALFORMED_ROW = "dependency_malformed_row"


# Gherkin-phrase -> typed-value lookups. Keeping these as module-level dicts
# lets each step body stay a single typed lookup + a single composition call
# (Mandate-12 criterion 3: no control flow in step bodies).

SECOND_ROW_SHAPE_BY_ANNOTATION_PHRASE: dict[str, SecondRowShape] = {
    "no annotation": SecondRowShape.NO_ANNOTATION,
    "@walking_skeleton": SecondRowShape.WALKING_SKELETON,
    "@infrastructure": SecondRowShape.INFRASTRUCTURE,
}

# The dependency-row scenarios vary only in whether the Justification cell is
# empty -- one phrase axis, shared by the accepted and rejected scenarios
# (Mandate-12 step reuse: one Given step body serves both).
DEPENDENCY_ROW_SHAPE_BY_JUSTIFICATION_PHRASE: dict[str, SecondRowShape] = {
    "a non-empty": SecondRowShape.DEPENDENCY_JUSTIFIED,
    "an empty": SecondRowShape.DEPENDENCY_UNJUSTIFIED,
}

VERDICT_BY_PHRASE: dict[str, DependencyVerdict] = {
    "accepted": DependencyVerdict.ACCEPTED,
    "rejected for an unjustified feature dependency": (
        DependencyVerdict.UNJUSTIFIED_FEATURE_DEPENDENCY
    ),
    "rejected for a malformed Feature Plan": DependencyVerdict.MALFORMED_FEATURE_PLAN,
    "rejected for an unjustified slice dependency": (
        DependencyVerdict.UNJUSTIFIED_SLICE_DEPENDENCY
    ),
}

CHECK_MODE_BY_PHRASE: dict[str, CheckMode] = {
    "the feature-plan check": CheckMode.FEATURE_PLAN,
    "the slice-plan check": CheckMode.SLICE_PLAN,
}
