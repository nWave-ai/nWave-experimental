"""Domain types for slice-01 of `slice-dependency-declared` (mikado node D94).

Every domain noun the Gherkin uses is expressed once here as a typed enum or
NewType; step bodies and the composition service consume these typed
parameters (Mandate-12 criterion 1).

slice-01 wires ONE new resolution function, `resolve_predecessor_slice`, into
the M8 carpaccio-order check: an entering slice's predecessor is its OWN
Slice-Plan row's declared `depends-on {slice-id}` target when well-formed,
falling back to the pre-existing `slice-(N-1)` positional default on silence,
absence, or an unreadable/malformed plan -- and blocking LOUD, never silently
falling back, on a malformed-but-present declaration.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "declared-dependency-demo").
FeatureId = NewType("FeatureId", str)

# A carpaccio slice identifier (e.g. "slice-03").
SliceId = NewType("SliceId", str)


class HookVerdict(str, Enum):
    """The user-observable verdict of the M8 carpaccio order check.

    ALLOWED -- the order check found the resolved predecessor's ledger record
               (or found no predecessor at all) and let the dispatch through.
    BLOCKED -- the order check refused the dispatch: an unsatisfied
               predecessor (declared or positional) or a malformed
               declaration.
    """

    ALLOWED = "allowed"
    BLOCKED = "blocked"


class PlanShape(str, Enum):
    """The degraded/edge shape of the feature-delta.md fixture the entering
    slice's own row is read from (CT-1 + CT-7's Universe).

    Every shape below MUST degrade to the SAME positional `slice-(N-1)`
    fallback as today's pre-feature behaviour -- never a new block class,
    never a crash.

    NO_FILE                  -- feature-delta.md does not exist at all
                                 (CT-1's "no plan" AND CT-7's "file absent").
    NO_SLICE_PLAN_SECTION     -- the file exists but carries no
                                 `## Wave: DISCUSS / [REF] Slice Plan`
                                 heading (CT-7's GateError(1)).
    MALFORMED_TABLE           -- the heading is present but no parseable table
                                 rows follow it (CT-7's GateError(2)).
    PATH_IS_DIRECTORY         -- the feature-delta.md path is a directory, so
                                 reading it raises OSError (CT-7's
                                 "unreadable").
    ROW_ABSENT                -- a well-formed Slice Plan exists but carries
                                 no row at all for the entering slice
                                 (CT-1's "plan-no-row").
    ANNOTATION_EMPTY          -- the entering slice's own row exists with an
                                 empty Annotation cell (CT-1's
                                 "row-no-annotation" / "row-annotation-no-
                                 depends-on").
    """

    NO_FILE = "no_file"
    NO_SLICE_PLAN_SECTION = "no_slice_plan_section"
    MALFORMED_TABLE = "malformed_table"
    PATH_IS_DIRECTORY = "path_is_directory"
    ROW_ABSENT = "row_absent"
    ANNOTATION_EMPTY = "annotation_empty"


# Gherkin-phrase -> typed-value lookups (Mandate-12 criterion 3: no control
# flow in step bodies -- each body is a single typed lookup + composition
# call).

PLAN_SHAPE_BY_PHRASE: dict[str, PlanShape] = {
    "absent (no feature-delta.md at all)": PlanShape.NO_FILE,
    "present but has no Slice Plan section": PlanShape.NO_SLICE_PLAN_SECTION,
    "present with a malformed Slice Plan table": PlanShape.MALFORMED_TABLE,
    "unreadable (the path is a directory)": PlanShape.PATH_IS_DIRECTORY,
    "missing the entering slice's own row": PlanShape.ROW_ABSENT,
    "silent on the entering slice's own row": PlanShape.ANNOTATION_EMPTY,
}

VERDICT_BY_PHRASE: dict[str, HookVerdict] = {
    "allowed": HookVerdict.ALLOWED,
    "blocked": HookVerdict.BLOCKED,
}
