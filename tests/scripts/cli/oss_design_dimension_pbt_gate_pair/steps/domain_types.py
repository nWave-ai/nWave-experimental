"""Domain types for the design-dimension coverage CLI acceptance slice-01.

F-OSS-UPSTREAM-WAVE-GATE-PAIRS pair-1 (DESIGN-dimensions <-> DISTILL-pbt),
Mandate-12 criterion 1. Every domain noun used in the Gherkin is expressed
once here as a typed enum or NewType. Step bodies and the composition service
consume these typed parameters -- no raw ``str`` where a domain enum exists.

Walking-skeleton scope (slice-01): the existence-join half of the gate.
Several feature-delta shapes (all-witnessed / one-unwitnessed / empty-block /
absent-corpus), three verdicts (PASS / INDETERMINATE / MALFORMED), one
preservation universe (Mandate 8). The vocabulary is the SSOT shared between
the .feature file phrases and the composition fixtures.

The deeper P3 perturbation-witness ("a property name-matches a dimension but
asserts a constant -> flagged as not earned-witnessed") is slice-04 territory
(DIM-8, reuses the sibling ClauseWitnessPort); slice-01 witnesses EXISTENCE of
a carrier comment only -- a syntactic join, not a behavioral one.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "design-dimension-coverage-demo").
FeatureId = NewType("FeatureId", str)


class DimensionCoverageVerdict(str, Enum):
    """User-observable verdict of one check_design_dimension_coverage invocation.

    The CLI emits a single-line stdout token (the machine contract):

        ``design_dimension_coverage feature=<id> dimensions=<n> witnessed=<m> verdict=<PASS|INDETERMINATE|MALFORMED>``

    The verdict is read from the STRUCTURED ``verdict=`` token, never from
    free-text stdout substrings.

    Accepted verdict (exit 0):
    PASS              -- the feature-delta declares >=1 DESIGN dimension AND
                         every declared dimension-ID is witnessed by >=1
                         ``# dimension: DIM-N`` carrier comment in the AT
                         corpus (n >= 1 AND m == n).

    Soft-refusal verdict (exit 1, NON-HALTING at the hook):
    INDETERMINATE     -- >=1 declared dimension-ID has zero witnessing carrier
                         comments. The DISTILL-exit hook EMITS the loud warning
                         and ALLOWS the DISTILL->DELIVER move; it NEVER blocks
                         (OSS hooks-only ACL invariant, DIM-5).

    Error verdict (exit 2, NON-HALTING at the hook):
    MALFORMED         -- no parseable DESIGN dimensions block (heading absent,
                         table absent, or zero data rows -> empty block is
                         MALFORMED, never a vacuous all-witnessed PASS) OR the
                         AT-corpus root path does not exist.

    UNRECOGNISED_INVOCATION -- NO stdout token at all: the CLI did not produce
                         its single-line contract output. On master the
                         production CLI does not exist (or is a RED scaffold
                         raising AssertionError before printing), so the
                         invocation lands here. NOT a real verdict -- it is the
                         RED-for-the-right-reason signal (Mandate 7).
    """

    PASS = "pass"
    INDETERMINATE = "indeterminate"
    MALFORMED = "malformed"
    UNRECOGNISED_INVOCATION = "unrecognised_invocation"


class DimensionsHeadingStyle(str, Enum):
    """The heading the DESIGN dimensions block lives under (heading SSOT).

    DESIGN default #1 (ratified by Ale): the gate parser anchors on BOTH the
    canonical heading and the carpaccio-variant heading, via a regex mirroring
    the reuse-first gate's ``_REUSE_ANALYSIS_HEADING_RE``. slice-01 exercises
    BOTH so the heading-SSOT contract is pinned at the walking-skeleton layer.

    CANONICAL  -- ``## DESIGN Dimensions``.
    CARPACCIO  -- ``## Wave: DESIGN / [REF] Dimensions``.
    """

    CANONICAL = "canonical"
    CARPACCIO = "carpaccio"


class FeatureCorpusShape(str, Enum):
    """The shape of the feature-delta + AT corpus the gate is run against.

    Five walking-skeleton shapes covering the slice-01 existence-join
    decision space:

    ALL_DIMENSIONS_WITNESSED       -- the feature-delta declares two dimensions
                                      (DIM-1, DIM-2) under a DESIGN Dimensions
                                      block; the AT corpus carries a
                                      ``# dimension: DIM-1`` AND a
                                      ``# dimension: DIM-2`` carrier comment.
                                      Every declared dimension is witnessed ->
                                      PASS (DIM-1 parse + existence join GREEN).

    ONE_DIMENSION_UNWITNESSED      -- the feature-delta declares two dimensions
                                      (DIM-1, DIM-2); the corpus carries only a
                                      ``# dimension: DIM-1`` comment. DIM-2 has
                                      zero carriers -> INDETERMINATE-loud
                                      (DIM-3 core coverage value).

    ALL_DIMENSIONS_WITNESSED_CARPACCIO -- identical to ALL_DIMENSIONS_WITNESSED
                                      but the dimensions block lives under the
                                      carpaccio heading ``## Wave: DESIGN /
                                      [REF] Dimensions`` -> PASS (heading-SSOT
                                      contract, DESIGN default #1).

    EMPTY_DIMENSIONS_BLOCK         -- the feature-delta carries the DESIGN
                                      Dimensions heading + table header but ZERO
                                      data rows. An empty block is MALFORMED,
                                      never a vacuous all-witnessed PASS
                                      (non-vacuity invariant (a), DIM-7-adjacent
                                      -- the walking-skeleton MALFORMED probe).

    ABSENT_AT_CORPUS               -- the feature-delta declares dimensions but
                                      the ``--at-corpus-root`` directory does
                                      not exist. MALFORMED (corpus path missing
                                      -- earned-trust probe: never silent-pass
                                      an empty join as "all witnessed").
    """

    ALL_DIMENSIONS_WITNESSED = "all_dimensions_witnessed"
    ONE_DIMENSION_UNWITNESSED = "one_dimension_unwitnessed"
    ALL_DIMENSIONS_WITNESSED_CARPACCIO = "all_dimensions_witnessed_carpaccio"
    EMPTY_DIMENSIONS_BLOCK = "empty_dimensions_block"
    ABSENT_AT_CORPUS = "absent_at_corpus"

    # --- slice-02 shapes (report granularity + column-1 non-vacuity) --------
    # DIM-4: a named-and-summarised dimension is unwitnessed -- the report must
    # resolve DIM-N (summary), not the bare DIM-N. The summary text is the
    # comprehension-key the operator reads to know WHICH behavior axis is
    # uncovered.
    UNWITNESSED_DIMENSION_NAMED_IN_REPORT = "unwitnessed_dimension_named_in_report"

    # DIM-6: a declared dimension whose ID also appears ONLY in a prose /
    # rationale cell of the dimensions block. The prose-cell mention does NOT
    # satisfy the join (column-1 read only); the dimension stays unwitnessed and
    # the report still resolves its summary -- proving the prose mention is
    # non-vacuous, not a silent witness.
    PROSE_CELL_MENTION_DOES_NOT_WITNESS = "prose_cell_mention_does_not_witness"

    # DIM-7: a dimensions block whose only rows carry a BLANK / non-DIM
    # column-1 (structurally present rows, vacuous join key). This is MALFORMED
    # -- a vacuous column-1 is never a silent zero-dimensions PASS -- and the
    # report must name the column-1 vacuity reason, not an undifferentiated
    # either/or.
    VACUOUS_COLUMN_ONE_BLOCK = "vacuous_column_one_block"


# Gherkin-phrase -> typed-value lookups. Module-level dicts keep each step
# body a single typed lookup + a single composition call (Mandate-12
# criterion 3: no control flow in step bodies).

CORPUS_SHAPE_BY_PHRASE: dict[str, FeatureCorpusShape] = {
    "every declared dimension is witnessed by a property in the corpus": (
        FeatureCorpusShape.ALL_DIMENSIONS_WITNESSED
    ),
    "one declared dimension has no witnessing property in the corpus": (
        FeatureCorpusShape.ONE_DIMENSION_UNWITNESSED
    ),
    "every declared dimension is witnessed and the dimensions live under the "
    "carpaccio heading": (FeatureCorpusShape.ALL_DIMENSIONS_WITNESSED_CARPACCIO),
    "a dimensions block with the heading but no declared dimensions": (
        FeatureCorpusShape.EMPTY_DIMENSIONS_BLOCK
    ),
    "declared dimensions but no acceptance-test corpus on disk": (
        FeatureCorpusShape.ABSENT_AT_CORPUS
    ),
}

VERDICT_BY_PHRASE: dict[str, DimensionCoverageVerdict] = {
    "passes the design-dimension coverage check": DimensionCoverageVerdict.PASS,
    "is reported as having an unwitnessed dimension": (
        DimensionCoverageVerdict.INDETERMINATE
    ),
    "is reported as malformed": DimensionCoverageVerdict.MALFORMED,
}

# The exit code each verdict maps to (the Gate Contract machine surface).
# The Then-step reads the observable exit code against this typed mapping
# (no inline number literals in step bodies -- Mandate-12 criterion 3).
EXIT_CODE_BY_VERDICT: dict[DimensionCoverageVerdict, int] = {
    DimensionCoverageVerdict.PASS: 0,
    DimensionCoverageVerdict.INDETERMINATE: 1,
    DimensionCoverageVerdict.MALFORMED: 2,
}


# --- slice-02 vocabulary (report granularity + column-1 non-vacuity) --------
# The dimension-ID + its summary text the slice-02 fixtures declare. The
# report-resolution contract (DIM-4) requires the operator-facing report to
# resolve the dimension-ID to its summary text -- so the AT asserts BOTH the ID
# and the summary appear in the report, never the bare ID alone. These are the
# SSOT for the fixture's declared dimension + the expected report tokens.
UNWITNESSED_DIMENSION_ID = "DIM-OVERSIZE"
UNWITNESSED_DIMENSION_SUMMARY = "oversize config rejected"

# slice-02 Given-phrase -> typed corpus-shape lookup. Distinct phrasing from
# slice-01 (S1 step-text-uniqueness: no literal-arg collision across step files
# in the same feature dir).
SLICE_02_CORPUS_SHAPE_BY_PHRASE: dict[str, FeatureCorpusShape] = {
    "a declared dimension named in the block that no property witnesses": (
        FeatureCorpusShape.UNWITNESSED_DIMENSION_NAMED_IN_REPORT
    ),
    "a declared dimension whose identifier also appears only in a prose cell": (
        FeatureCorpusShape.PROSE_CELL_MENTION_DOES_NOT_WITNESS
    ),
    "a dimensions block whose only rows carry a blank identifier column": (
        FeatureCorpusShape.VACUOUS_COLUMN_ONE_BLOCK
    ),
}
