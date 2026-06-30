"""Domain types for the discuss-epic-mode slice-03 acceptance slice.

Feature: ``des validate-feature-delta --require-feature-plan --format=json`` on
an epic-delta rejects an infrastructure-only epic. discuss-epic-mode slice-03
(feature-granularity cohesion-MECC) + the DESIGN slice-03 code-design
(Mandate-12 criterion 1). Every domain noun used in the Gherkin is expressed once
here as a typed enum or NewType. Step bodies and the composition service consume
these typed parameters -- no raw ``str`` where a domain enum exists.

S1 step-text uniqueness: the slice-01 sibling suite
(``atdd_pure_validate_feature_delta_feature_plan``) speaks "a well-formed Feature
Plan" / "the Feature Plan is accepted"; the slice-plan suite
(``atdd_pure_validate_feature_delta_slice_plan``) speaks "slice plan". THIS suite
speaks the cohesion vocabulary -- "every feature is infrastructure" / "the epic is
rejected as infrastructure-only" / "the rejection names the cause in feature
terms" / "the cohesion check leaves the epic-delta unchanged". The domain nouns
differ, so the step phrases never collide across the three suites.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case epic identifier (e.g. "flow-v2-wave-migrations").
EpicId = NewType("EpicId", str)


class CohesionVerdict(str, Enum):
    """Maintainer-observable verdict of one feature-plan cohesion check.

    The ``--require-feature-plan --format=json`` mode emits a single JSON object
    whose ``verdict`` field is read as a STRUCTURED token (never a free-text
    stdout substring). The slice-03 cohesion concern distinguishes exactly two
    maintainer-observable outcomes over a well-formed five-column Feature Plan:

    REJECTED_INFRA_ONLY  -- token ``rejected-infra-only``: EVERY feature row's
                            Annotation normalises to ``@infrastructure``; the epic
                            carries no user-visible value and is vetoed by the
                            MECC floor (exit 1). The token is SHARED with the
                            slice-plan mode -- it names the failure CLASS, not the
                            plan kind; the detail's "feature rows" is the
                            plan-kind disambiguator (token-coupling H3/M1).
    CLEARS_FLOOR         -- token ``accepted``: at least one feature is
                            value-bearing (empty annotation, @walking-skeleton, or
                            any non-infra token), so the epic carries shippable
                            value and clears the cohesion floor (exit 0).
    UNRECOGNISED         -- NO structured ``verdict`` token in stdout: the CLI
                            produced no JSON object (e.g. an unknown flag prints a
                            usage banner). Used to fail loudly rather than silently
                            default; not a real cohesion verdict.
    """

    REJECTED_INFRA_ONLY = "rejected_infra_only"
    CLEARS_FLOOR = "clears_floor"
    UNRECOGNISED = "unrecognised"


class CohesionShape(str, Enum):
    """The cohesion shape of the Feature Plan the validator inspects.

    All three shapes are STRUCTURALLY well formed (R1 heading + the five fixed
    columns + >= 1 feature row); they differ only in the Annotation column, which
    is what the cohesion-MECC floor reads.

    ALL_INFRASTRUCTURE   -- many feature rows, EVERY one annotated
                            @infrastructure -- the infrastructure-only epic
                            (slice-03 AT-1).
    ONE_VALUE_BEARING    -- several @infrastructure rows plus exactly one
                            value-bearing row (empty annotation) -- the mixed epic
                            that clears the floor (slice-03 AT-2).
    SINGLE_INFRASTRUCTURE -- a single feature row, annotated @infrastructure --
                            still an infrastructure-only epic at cardinality one
                            (slice-03 AT-3, C3 Count: One).
    """

    ALL_INFRASTRUCTURE = "all_infrastructure"
    ONE_VALUE_BEARING = "one_value_bearing"
    SINGLE_INFRASTRUCTURE = "single_infrastructure"


# Gherkin-phrase -> typed-value lookups. Module-level dicts keep each step body a
# single typed lookup + a single composition call (Mandate-12 criterion 3: no
# control flow in step bodies).

COHESION_SHAPE_BY_PHRASE: dict[str, CohesionShape] = {
    "a Feature Plan whose every feature is infrastructure": (
        CohesionShape.ALL_INFRASTRUCTURE
    ),
    "a Feature Plan with one value-bearing feature among infrastructure": (
        CohesionShape.ONE_VALUE_BEARING
    ),
    "a Feature Plan with a single infrastructure feature": (
        CohesionShape.SINGLE_INFRASTRUCTURE
    ),
}
