"""Step definitions: a slice plan reads parallel-safe by default; a declared
dependency must justify itself.

`docs/feature/parallel-by-default-slice-plan/feature-delta.md` D-1..D-6 /
slice-01.

Layer 3 (subprocess/FS acceptance). Example-only, no PBT machinery
(Mandate 9/11): the Annotation vocabulary forms a finite, enumerable closed
set (no annotation / @walking_skeleton / @infrastructure / @coupled /
depends-on justified / depends-on unjustified / depends-on malformed), so a
`Scenario Outline` over that set is the correct paradigm.

The validator has a pure-function contract (it reads the document and
returns a verdict). Every When-step captures the universe first so the
Then-step can assert via `assert_state_delta` that the document was NOT
mutated (Mandate 8).

Step bodies delegate to `SliceDependencyJustificationComposition`; no inline
business logic (Mandate-12 criterion 3) -- each body is a typed lookup plus a
composition call.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .composition import (
    SliceDependencyJustificationComposition,
    ValidationResult,
)
from .domain_types import (
    CHECK_MODE_BY_PHRASE,
    DEPENDENCY_ROW_SHAPE_BY_JUSTIFICATION_PHRASE,
    SECOND_ROW_SHAPE_BY_ANNOTATION_PHRASE,
    VERDICT_BY_PHRASE,
    CheckMode,
    FeatureId,
    SecondRowShape,
)


scenarios("../slice-dependency-justification.feature")


@pytest.fixture
def composition(tmp_path: Path) -> SliceDependencyJustificationComposition:
    """Production-wired composition root over a tmp_path repository."""
    return SliceDependencyJustificationComposition(repo_dir=tmp_path / "repo")


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for the validation result + universe across When -> Then steps."""
    return {}


# --- Given ---------------------------------------------------------------


@given("a feature-delta authored for an atdd_pure feature")
def given_feature(composition: SliceDependencyJustificationComposition) -> None:
    composition.create_feature(FeatureId("parallel-by-default-slice-plan"))


@given(
    parsers.parse(
        "the feature-delta carries a slice plan whose second row carries "
        "{annotation} and an empty Justification"
    )
)
def given_slice_plan_second_row(
    composition: SliceDependencyJustificationComposition, annotation: str
) -> None:
    composition.provision_slice_plan(SECOND_ROW_SHAPE_BY_ANNOTATION_PHRASE[annotation])


@given(
    parsers.parse(
        "the feature-delta carries a slice plan whose second row declares "
        "depends-on slice-01 with {justification_state} Justification"
    )
)
def given_slice_plan_dependency_row(
    composition: SliceDependencyJustificationComposition, justification_state: str
) -> None:
    composition.provision_slice_plan(
        DEPENDENCY_ROW_SHAPE_BY_JUSTIFICATION_PHRASE[justification_state]
    )


@given(
    "the feature-delta carries a slice plan whose second row is a "
    "dependency-shaped row missing its Justification column entirely"
)
def given_slice_plan_malformed_dependency_row(
    composition: SliceDependencyJustificationComposition,
) -> None:
    composition.provision_slice_plan(SecondRowShape.DEPENDENCY_MALFORMED_ROW)


@given(
    "an epic-delta whose feature plan carries a depends-on row with an "
    "empty Justification"
)
def given_epic_feature_plan(
    composition: SliceDependencyJustificationComposition,
) -> None:
    composition.provision_feature_plan_with_unjustified_dependency()


# --- When ------------------------------------------------------------------


@when(parsers.parse("the Product Owner runs {check_mode} on the feature-delta"))
def when_run_slice_plan_check(
    composition: SliceDependencyJustificationComposition,
    result_box: dict[str, object],
    check_mode: str,
) -> None:
    result_box["universe_before"] = composition.capture_universe()
    result_box["result"] = composition.run_check(CHECK_MODE_BY_PHRASE[check_mode])


@when("the maintainer runs the feature-plan check on the epic-delta")
def when_run_feature_plan_check(
    composition: SliceDependencyJustificationComposition,
    result_box: dict[str, object],
) -> None:
    result_box["universe_before"] = composition.capture_universe()
    result_box["result"] = composition.run_check(CheckMode.FEATURE_PLAN)


# --- Then --------------------------------------------------------------------


@then(parsers.parse("the slice plan is {verdict_phrase}"))
def then_slice_plan_verdict(result_box: dict[str, object], verdict_phrase: str) -> None:
    result = result_box["result"]
    assert isinstance(result, ValidationResult)
    assert result.verdict is VERDICT_BY_PHRASE[verdict_phrase]


@then(parsers.parse("the feature plan is {verdict_phrase}"))
def then_feature_plan_verdict(
    result_box: dict[str, object], verdict_phrase: str
) -> None:
    result = result_box["result"]
    assert isinstance(result, ValidationResult)
    assert result.verdict is VERDICT_BY_PHRASE[verdict_phrase]


@then("the rejection names the offending row")
def then_rejection_names_offending_row(result_box: dict[str, object]) -> None:
    """GDP-3: the diagnostic names WHAT failed -- the specific row that
    declared a dependency without backing it, and WHY (the empty
    Justification cell). This fixture's offending row is the second data
    row under the Slice Plan header (row_no=2 in the per-row classifier
    loop, per the DESIGN section's own cited detail format:
    `f"row {row_no} declares 'depends-on' with an empty Justification cell
    (D-1/D-2)"`), so `row 2` is the row-number witness, not the Slice
    column's own `slice-02` identifier (a different cell of the same row)."""
    result = result_box["result"]
    assert isinstance(result, ValidationResult)
    assert "row 2" in result.detail
    assert "justification" in result.detail.lower()


@then("the check leaves the feature-delta unchanged")
def then_feature_delta_unchanged(
    composition: SliceDependencyJustificationComposition,
    result_box: dict[str, object],
) -> None:
    """Pure-function contract: the validator mutates no file (Mandate 8)."""
    assert_state_delta(
        before=result_box["universe_before"],  # type: ignore[arg-type]
        after=composition.capture_universe(),
        universe={"document.exists", "document.bytes"},
        expected={
            "document.exists": unchanged(),
            "document.bytes": unchanged(),
        },
    )
