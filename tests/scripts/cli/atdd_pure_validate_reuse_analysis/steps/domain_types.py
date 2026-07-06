"""Domain types for the Reuse Analysis gate acceptance slices.

F-DESIGN-REUSE-FIRST-GATE (DDD-1..DDD-11), Mandate-12 criterion 1. Every
domain noun used in the Gherkin is expressed once here as a typed enum or
NewType. Step bodies and the composition service consume these typed
parameters -- no raw ``str`` where a domain enum exists.

Shared across slice-01 (collected), slice-02 and slice-03 (parked) -- the
step-method vocabulary is one SSOT.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "reuse-gate-demo").
FeatureId = NewType("FeatureId", str)


class CheckMode(str, Enum):
    """How the validate-feature-delta CLI is invoked.

    PLAIN                  -- the existing heading-form-only invocation.
    REQUIRE_REUSE_ANALYSIS -- the F-DESIGN-REUSE-FIRST-GATE invocation
                              (``validate_feature_delta.py
                              --require-reuse-analysis --format=json <path>``).
                              Emits a single JSON object with a stable
                              ``verdict`` token.
    """

    PLAIN = "plain"
    REQUIRE_REUSE_ANALYSIS = "require_reuse_analysis"


class ReuseVerdict(str, Enum):
    """User-observable verdict of one Reuse Analysis check invocation (DDD-2).

    The CLI is invoked with ``--require-reuse-analysis --format=json`` and
    emits a single JSON object whose ``verdict`` field is one of a closed
    token set. The verdict is read from that STRUCTURED token, never from
    free-text stdout substrings.

    Accepted verdicts (exit 0):
    STRUCTURALLY_ACCEPTED  -- token ``structurally-accepted``: a well-formed
                              table. NOT a claim reuse-first was honoured
                              (DDD-3) -- only that the table is well formed.
    NO_OVERLAP_DECLARED    -- token ``no-overlap-declared``: the feature
                              declares it overlaps nothing via a
                              ``Reuse-Analysis: no-overlap`` marker (DDD-9).
    METHODOLOGY_EXEMPT     -- token ``methodology-exempt``: a methodology-only
                              feature declares exemption via a
                              ``Reuse-Analysis: methodology-exempt`` marker
                              (DDD-9).

    Rejected verdicts (exit 1):
    MISSING_REUSE_ANALYSIS -- token ``missing-reuse-analysis``: no Reuse
                              Analysis section and no exemption marker.
    MALFORMED_REUSE_ANALYSIS -- token ``malformed-reuse-analysis``: the
                              section exists but its table is unsound -- a
                              ``Decision`` not normalising into
                              {EXTEND, CREATE_NEW}, wrong columns, or a
                              duplicate ``## Reuse Analysis`` heading (DDD-11).
    UNJUSTIFIED_CREATE_NEW -- token ``unjustified-create-new``: a CREATE_NEW
                              row carries an empty ``Justification`` (DDD-3).
    MALFORMED_WAVE_HEADING -- token ``malformed-wave-heading``: a ``## Wave:``
                              heading violates the [REF|WHY|HOW] schema (the
                              pre-existing check, still enforced).

    UNRECOGNISED_INVOCATION -- NO structured ``verdict`` token in stdout: the
                              CLI did not produce JSON. On master the
                              ``--require-reuse-analysis`` flag is unknown, so
                              the invocation lands here. NOT a real verdict --
                              it is the regression RED signal.
    """

    STRUCTURALLY_ACCEPTED = "structurally_accepted"
    NO_OVERLAP_DECLARED = "no_overlap_declared"
    METHODOLOGY_EXEMPT = "methodology_exempt"
    MISSING_REUSE_ANALYSIS = "missing_reuse_analysis"
    MALFORMED_REUSE_ANALYSIS = "malformed_reuse_analysis"
    UNJUSTIFIED_CREATE_NEW = "unjustified_create_new"
    MALFORMED_WAVE_HEADING = "malformed_wave_heading"
    UNRECOGNISED_INVOCATION = "unrecognised_invocation"


class ReuseTableShape(str, Enum):
    """The shape of the Reuse Analysis section the validator inspects.

    slice-01 (walking skeleton) exercises the first three; slice-02 (parked)
    exercises the remainder.

    WELL_FORMED        -- the canonical ``## Reuse Analysis`` heading followed
                          by a five-column GFM table; every ``Decision`` is
                          a clean ``EXTEND`` -- the structural happy path.
    SECTION_ABSENT     -- the feature-delta has wave headings but no
                          ``## Reuse Analysis`` section and no exemption
                          marker (C1 zero-input / C3 zero-row case).
    THIS_FEATURE_GOLD  -- the gold test: a verbatim copy of THIS feature's own
                          Reuse Analysis table (bold cells, canonical heading,
                          five EXTEND rows) -- the dogfood acceptance case.
    UN_NORMALISABLE_DECISION -- a component row whose ``Decision`` cell does
                          not normalise into {EXTEND, CREATE_NEW} (DDD-7).
    CREATE_NEW_EMPTY_JUSTIFICATION -- a ``CREATE_NEW`` row with an empty
                          ``Justification`` cell (DDD-3).
    CREATE_NEW_SPACE_SPELLING -- a ``CREATE NEW`` (space) row that DDD-7
                          normalisation collapses to ``CREATE_NEW``; with a
                          non-empty justification it is accepted.
    METHODOLOGY_EXEMPT_MARKER -- no table; a ``Reuse-Analysis:
                          methodology-exempt`` marker under the heading
                          (DDD-9).
    NO_OVERLAP_MARKER  -- no table; a ``Reuse-Analysis: no-overlap`` marker
                          under the heading (DDD-9).
    DUPLICATE_HEADING  -- two ``## Reuse Analysis`` headings -- the second
                          occurrence is malformed (DDD-11).
    """

    WELL_FORMED = "well_formed"
    SECTION_ABSENT = "section_absent"
    THIS_FEATURE_GOLD = "this_feature_gold"
    UN_NORMALISABLE_DECISION = "un_normalisable_decision"
    CREATE_NEW_EMPTY_JUSTIFICATION = "create_new_empty_justification"
    CREATE_NEW_SPACE_SPELLING = "create_new_space_spelling"
    CREATE_NEW_PARENTHETICAL_QUALIFIER = "create_new_parenthetical_qualifier"
    METHODOLOGY_EXEMPT_MARKER = "methodology_exempt_marker"
    NO_OVERLAP_MARKER = "no_overlap_marker"
    DUPLICATE_HEADING = "duplicate_heading"


# Gherkin-phrase -> typed-value lookups. Module-level dicts keep each step body
# a single typed lookup + a single composition call (Mandate-12 criterion 3:
# no control flow in step bodies).

REUSE_TABLE_SHAPE_BY_PHRASE: dict[str, ReuseTableShape] = {
    "a well-formed Reuse Analysis table": ReuseTableShape.WELL_FORMED,
    "no Reuse Analysis section": ReuseTableShape.SECTION_ABSENT,
    "this feature's own Reuse Analysis table": ReuseTableShape.THIS_FEATURE_GOLD,
    "a component row with an un-normalisable Decision": (
        ReuseTableShape.UN_NORMALISABLE_DECISION
    ),
    "a CREATE_NEW row with an empty Justification": (
        ReuseTableShape.CREATE_NEW_EMPTY_JUSTIFICATION
    ),
    "a CREATE NEW row spelled with a space": (
        ReuseTableShape.CREATE_NEW_SPACE_SPELLING
    ),
    "a CREATE_NEW row with a trailing parenthetical qualifier": (
        ReuseTableShape.CREATE_NEW_PARENTHETICAL_QUALIFIER
    ),
    "a methodology-exempt marker": ReuseTableShape.METHODOLOGY_EXEMPT_MARKER,
    "a no-overlap marker": ReuseTableShape.NO_OVERLAP_MARKER,
    "a duplicate Reuse Analysis heading": ReuseTableShape.DUPLICATE_HEADING,
}

VERDICT_BY_PHRASE: dict[str, ReuseVerdict] = {
    "structurally accepted": ReuseVerdict.STRUCTURALLY_ACCEPTED,
    "accepted as declaring no overlap": ReuseVerdict.NO_OVERLAP_DECLARED,
    "accepted as methodology-exempt": ReuseVerdict.METHODOLOGY_EXEMPT,
    "rejected for a missing Reuse Analysis": ReuseVerdict.MISSING_REUSE_ANALYSIS,
    "rejected for a malformed Reuse Analysis": (ReuseVerdict.MALFORMED_REUSE_ANALYSIS),
    "rejected for an unjustified CREATE_NEW": ReuseVerdict.UNJUSTIFIED_CREATE_NEW,
}

CHECK_MODE_BY_PHRASE: dict[str, CheckMode] = {
    "the Reuse Analysis check": CheckMode.REQUIRE_REUSE_ANALYSIS,
    "the plain heading check": CheckMode.PLAIN,
}
