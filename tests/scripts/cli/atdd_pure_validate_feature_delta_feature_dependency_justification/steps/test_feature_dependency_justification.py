"""Step definitions: a Feature Plan row reads parallel-safe by default; a
declared feature dependency must justify itself.

`docs/feature/parallel-by-default-feature-plan/feature-delta.md` D-1..D-7 /
slice-01.

Layer 3 (subprocess/FS acceptance). Example-only, no PBT machinery
(Mandate 9/11): the Annotation vocabulary forms a finite, enumerable closed
set (no annotation / @walking_skeleton / @infrastructure / depends-on
justified / depends-on unjustified / depends-on malformed), so a
`Scenario Outline` over that set is the correct paradigm.

The validator has a pure-function contract (it reads the document and
returns a verdict). Every When-step captures the universe first so the
Then-step can assert via `assert_state_delta` that the document was NOT
mutated (Mandate 8).

Step bodies delegate to `FeatureDependencyJustificationComposition`; no
inline business logic (Mandate-12 criterion 3) -- each body is a typed
lookup plus a composition call.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .composition import (
    FeatureDependencyJustificationComposition,
    ValidationResult,
)
from .domain_types import (
    CHECK_MODE_BY_PHRASE,
    DEPENDENCY_ROW_SHAPE_BY_JUSTIFICATION_PHRASE,
    SECOND_ROW_SHAPE_BY_ANNOTATION_PHRASE,
    VERDICT_BY_PHRASE,
    CheckMode,
    EpicId,
    SecondRowShape,
)


scenarios("../feature-dependency-justification.feature")


@pytest.fixture
def composition(tmp_path: Path) -> FeatureDependencyJustificationComposition:
    """Production-wired composition root over a tmp_path repository."""
    return FeatureDependencyJustificationComposition(repo_dir=tmp_path / "repo")


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for the validation result + universe across When -> Then steps."""
    return {}


# --- Given ---------------------------------------------------------------


@given("an epic-delta authored for a multi-feature epic")
def given_epic(composition: FeatureDependencyJustificationComposition) -> None:
    composition.create_epic(EpicId("swarm-parallel-delivery"))


@given(
    parsers.parse(
        "the epic-delta carries a Feature Plan whose second row carries "
        "{annotation} and an empty Justification"
    )
)
def given_feature_plan_second_row(
    composition: FeatureDependencyJustificationComposition, annotation: str
) -> None:
    composition.provision_feature_plan(
        SECOND_ROW_SHAPE_BY_ANNOTATION_PHRASE[annotation]
    )


@given(
    parsers.parse(
        "the epic-delta carries a Feature Plan whose second row declares "
        "depends-on webhook-retry-core with {justification_state} Justification"
    )
)
def given_feature_plan_dependency_row(
    composition: FeatureDependencyJustificationComposition, justification_state: str
) -> None:
    composition.provision_feature_plan(
        DEPENDENCY_ROW_SHAPE_BY_JUSTIFICATION_PHRASE[justification_state]
    )


@given(
    "the epic-delta carries a Feature Plan whose second row is a "
    "dependency-shaped row missing its Justification column entirely"
)
def given_feature_plan_malformed_dependency_row(
    composition: FeatureDependencyJustificationComposition,
) -> None:
    composition.provision_feature_plan(SecondRowShape.DEPENDENCY_MALFORMED_ROW)


@given(
    "a feature-delta whose slice plan carries a depends-on row with an "
    "empty Justification"
)
def given_feature_delta_slice_plan(
    composition: FeatureDependencyJustificationComposition,
) -> None:
    composition.provision_slice_plan_with_unjustified_dependency()


# --- When ------------------------------------------------------------------


@when(parsers.parse("the maintainer runs {check_mode} on the epic-delta"))
def when_run_feature_plan_check(
    composition: FeatureDependencyJustificationComposition,
    result_box: dict[str, object],
    check_mode: str,
) -> None:
    result_box["universe_before"] = composition.capture_universe()
    result_box["result"] = composition.run_check(CHECK_MODE_BY_PHRASE[check_mode])


@when("the Product Owner runs the slice-plan check on the feature-delta")
def when_run_slice_plan_check(
    composition: FeatureDependencyJustificationComposition,
    result_box: dict[str, object],
) -> None:
    result_box["universe_before"] = composition.capture_universe()
    result_box["result"] = composition.run_check(CheckMode.SLICE_PLAN)


# --- Then --------------------------------------------------------------------


@then(parsers.parse("the Feature Plan is {verdict_phrase}"))
def then_feature_plan_verdict(
    result_box: dict[str, object], verdict_phrase: str
) -> None:
    result = result_box["result"]
    assert isinstance(result, ValidationResult)
    assert result.verdict is VERDICT_BY_PHRASE[verdict_phrase]


@then(parsers.parse("the slice plan is {verdict_phrase}"))
def then_slice_plan_verdict(result_box: dict[str, object], verdict_phrase: str) -> None:
    result = result_box["result"]
    assert isinstance(result, ValidationResult)
    assert result.verdict is VERDICT_BY_PHRASE[verdict_phrase]


@then("the rejection names the offending feature row")
def then_rejection_names_offending_row(result_box: dict[str, object]) -> None:
    """GDP-3: the diagnostic names WHAT failed -- the specific row that
    declared a dependency without backing it, and WHY (the empty
    Justification cell). This fixture's offending row is the second data
    row under the Feature Plan header (row_no=2 in the per-row classifier
    loop, the SAME generic, spec-independent detail format the slice-plan
    mode already emits: `f"row {row_no} declares 'depends-on' with an empty
    Justification cell (D-1/D-2)"`), so `row 2` is the row-number witness,
    not the Feature column's own `dunning-emails` identifier (a different
    cell of the same row)."""
    result = result_box["result"]
    assert isinstance(result, ValidationResult)
    assert "row 2" in result.detail
    assert "justification" in result.detail.lower()


@then("the check leaves the epic-delta unchanged")
def then_epic_delta_unchanged(
    composition: FeatureDependencyJustificationComposition,
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
