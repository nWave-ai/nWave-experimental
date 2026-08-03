"""Domain types for the mikado-board declared-status-render acceptance slice.

slice-01 of `unified-slice-progress-visualization` (DES-1/DES-2/DES-7,
Mandate-12 criterion 1). Every domain noun used in the Gherkin is expressed
once here as a typed enum or NewType. Step bodies and the composition service
consume these typed parameters -- no raw ``str`` where a domain enum exists.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "board-render-demo").
FeatureId = NewType("FeatureId", str)

# A Slice Plan row identifier (e.g. "slice-01").
SliceId = NewType("SliceId", str)


class DeclaredStatus(str, Enum):
    """The Slice Plan's Status column vocabulary (feature-delta.md Decision 2).

    PENDING -- the slice has not shipped yet.
    SHIPPED -- the slice has shipped.
    """

    PENDING = "pending"
    SHIPPED = "shipped"


class SlicePlanShape(str, Enum):
    """The shape of the Slice Plan section a fixture feature-delta carries.

    SECTION_ABSENT -- the feature-delta has no `[REF] Slice Plan` heading
                      at all (a structural omission, DDD-8 arity corollary).
    FOUR_COLUMNS   -- the section is present but its table has only four
                      columns instead of the required five (ADR-028 D2).
    ZERO_ROWS      -- the section is present with a well-formed five-column
                      header, but ZERO slice rows (C3 zero-obligation: the
                      `slices` render output is an iterative surface, and
                      this is its explicit empty-input boundary case).
    """

    SECTION_ABSENT = "section_absent"
    FOUR_COLUMNS = "four_columns"
    ZERO_ROWS = "zero_rows"


class RenderVerdict(str, Enum):
    """User-observable verdict of one `des mikado-board render` invocation.

    The CLI is invoked with ``--format=json`` and emits a single JSON object
    whose ``verdict`` field is one of the closed token set below (mirroring
    the `--require-slice-plan --format=json` convention already established
    by `validate_feature_delta.py`). The verdict is read from that
    STRUCTURED token, never from free-text stdout substrings.

    RENDERED               -- token ``rendered``: the Slice Plan was read and
                               every slice's declared status is present in
                               the response, in document order.
    MISSING_FEATURE_DELTA  -- token ``missing-feature-delta``: no
                               feature-delta.md exists for the given
                               feature-id under --repo-root.
    MISSING_SLICE_PLAN     -- token ``missing-slice-plan``: the feature-delta
                               exists but carries no `[REF] Slice Plan`
                               section at all.
    MALFORMED_SLICE_PLAN   -- token ``malformed-slice-plan``: the section
                               exists but its table is not the well-formed
                               five-column shape.
    UNRECOGNISED_INVOCATION -- NO structured ``verdict`` token in stdout: the
                               CLI did not produce JSON output. On master
                               ``mikado-board`` is not yet a registered `des`
                               subcommand, so every invocation lands here --
                               this is the regression RED signal, NOT a real
                               verdict.
    """

    RENDERED = "rendered"
    MISSING_FEATURE_DELTA = "missing_feature_delta"
    MISSING_SLICE_PLAN = "missing_slice_plan"
    MALFORMED_SLICE_PLAN = "malformed_slice_plan"
    UNRECOGNISED_INVOCATION = "unrecognised_invocation"


# Gherkin-phrase -> typed-value lookups. Keeping these as module-level dicts
# lets each step body stay a single typed lookup + a single composition call
# (Mandate-12 criterion 3: no control flow in step bodies).

SLICE_PLAN_SHAPE_BY_PHRASE: dict[str, SlicePlanShape] = {
    "no slice-plan section at all": SlicePlanShape.SECTION_ABSENT,
    "a slice plan with only four columns": SlicePlanShape.FOUR_COLUMNS,
    "a slice plan with a header but zero slice rows": SlicePlanShape.ZERO_ROWS,
}

CAUSE_BY_PHRASE: dict[str, RenderVerdict] = {
    "a missing slice plan": RenderVerdict.MISSING_SLICE_PLAN,
    "a malformed slice plan": RenderVerdict.MALFORMED_SLICE_PLAN,
}
