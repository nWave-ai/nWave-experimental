"""Domain types for the discuss-epic-mode slice-01 acceptance slice.

Feature: ``des validate-feature-delta --require-feature-plan --format=json`` on
an epic-delta emits a closed verdict. discuss-epic-mode R1 (Feature Plan heading)
+ R2 (Status tokens) + the slice-01 code-design parametrization (Mandate-12
criterion 1). Every domain noun used in the Gherkin is expressed once here as a
typed enum or NewType. Step bodies and the composition service consume these
typed parameters -- no raw ``str`` where a domain enum exists.

S1 step-text uniqueness: the slice-plan sibling suite
(``tests/scripts/cli/atdd_pure_validate_feature_delta_slice_plan``) speaks
"slice plan" / "Product Owner runs the slice-plan check"; this suite speaks
"Feature Plan" / "maintainer runs the feature-plan check on the epic-delta".
The domain nouns differ, so the step phrases never collide.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case epic identifier (e.g. "flow-v2-wave-migrations").
EpicId = NewType("EpicId", str)


class FeaturePlanVerdict(str, Enum):
    """Maintainer-observable verdict of one feature-plan check invocation.

    The ``--require-feature-plan --format=json`` mode emits a single JSON object
    whose ``verdict`` field is one of the slice-01 closed token set
    (discuss-epic-mode R1 / slice-01 code-design):

        accepted | missing-feature-plan | malformed-feature-plan
                 | malformed-wave-heading

    (``rejected-infra-only`` is the slice-03 cohesion-MECC concern, NOT a
    slice-01 verdict -- excluded from this set by scope.) The verdict is read
    from that STRUCTURED token, never from free-text stdout substrings.

    ACCEPTED                 -- token ``accepted``: the epic-delta carries a
                                well-formed Feature Plan (R1 heading + the five
                                fixed columns + >= 1 value-bearing row).
    MISSING_FEATURE_PLAN     -- token ``missing-feature-plan``: the
                                ``[REF] Feature Plan`` section is absent.
    MALFORMED_FEATURE_PLAN   -- token ``malformed-feature-plan``: the section
                                exists but its table is not the fixed
                                five-column shape -- wrong column count, columns
                                reordered, or zero feature rows.
    MALFORMED_WAVE_HEADING   -- token ``malformed-wave-heading``: a ``## Wave:``
                                heading violates the D2 [REF|WHY|HOW] schema (the
                                pre-existing check, shared by both plan modes).
    UNRECOGNISED_INVOCATION  -- NO structured ``verdict`` token in stdout: the
                                CLI produced no JSON object. On the current tip
                                the ``--require-feature-plan`` flag is unknown,
                                so every feature-plan invocation lands here --
                                the active-RED missing-functionality signal, NOT
                                a real verdict.
    """

    ACCEPTED = "accepted"
    MISSING_FEATURE_PLAN = "missing_feature_plan"
    MALFORMED_FEATURE_PLAN = "malformed_feature_plan"
    MALFORMED_WAVE_HEADING = "malformed_wave_heading"
    UNRECOGNISED_INVOCATION = "unrecognised_invocation"


class FeaturePlanShape(str, Enum):
    """The shape of the Feature Plan section the validator inspects.

    WELL_FORMED        -- the canonical R1 ``[REF] Feature Plan`` heading
                          followed by a five-column GFM table (Feature, Value
                          statement, Status, Annotation, Justification) with
                          >= 1 value-bearing feature row -- the structural happy
                          path (slice-01 AT-1, the walking skeleton).
    SECTION_ABSENT     -- the epic-delta has wave headings but no
                          ``[REF] Feature Plan`` heading at all (slice-01 AT-2).
    FOUR_COLUMNS       -- the section is present but its table has only four
                          columns instead of the required five (slice-01 AT-3:
                          one named malformed defect).
    COLUMNS_REORDERED  -- a five-column table whose columns appear in a different
                          order. The Feature Plan reuses the D2 "fixed order"
                          contract (R1), so a re-order is a malformed feature
                          plan (slice-01 AT-3: the second named malformed defect).
    """

    WELL_FORMED = "well_formed"
    SECTION_ABSENT = "section_absent"
    FOUR_COLUMNS = "four_columns"
    COLUMNS_REORDERED = "columns_reordered"


# Gherkin-phrase -> typed-value lookups. Keeping these as module-level dicts
# lets each step body stay a single typed lookup + a single composition call
# (Mandate-12 criterion 3: no control flow in step bodies).

FEATURE_PLAN_SHAPE_BY_PHRASE: dict[str, FeaturePlanShape] = {
    "a well-formed Feature Plan": FeaturePlanShape.WELL_FORMED,
    "no Feature Plan section": FeaturePlanShape.SECTION_ABSENT,
    "a Feature Plan with only four columns": FeaturePlanShape.FOUR_COLUMNS,
    "a Feature Plan whose table has the columns reordered": (
        FeaturePlanShape.COLUMNS_REORDERED
    ),
}

VERDICT_BY_PHRASE: dict[str, FeaturePlanVerdict] = {
    "accepted": FeaturePlanVerdict.ACCEPTED,
    "rejected for a missing Feature Plan": (FeaturePlanVerdict.MISSING_FEATURE_PLAN),
    "rejected for a malformed Feature Plan": (
        FeaturePlanVerdict.MALFORMED_FEATURE_PLAN
    ),
}
