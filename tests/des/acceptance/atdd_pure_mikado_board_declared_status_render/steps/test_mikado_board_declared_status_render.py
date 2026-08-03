"""Step definitions: slice-01 -- the mikado-board declared-status render.

slice-01 of `unified-slice-progress-visualization` (JOB-028, D4/D5,
DES-1/DES-2/DES-7). Max parametrize density within a right-sized walking
skeleton (Mandate 9/11, layer-2 example-only Gherkin -- the paired Hypothesis
property test in this same directory carries the layer-1/2 PBT-full
invariant, Mandate 9):

  * walking-skeleton (`@wiring_e2e @walking_skeleton`) -- the ONE
    subprocess-e2e for this whole feature: the real installed `des` CLI
    renders two slices' declared statuses verbatim.
  * single-slice / many-slice boundary scenarios -- C1/C3 cardinality.
  * never-stale negative scenario -- proves the projection is composed
    fresh on every read (DES-1), never cached.
  * missing-feature-delta / missing-or-malformed-slice-plan error
    scenarios -- the two `failure_modes` named in the DISCUSS journey
    (journey-trustworthy-parallel-view.yaml step 1).

Layer 2 (in-process acceptance) -- example-only, no PBT machinery here
(Mandate 9/11). Step bodies delegate to `MikadoBoardRenderComposition`; no
inline logic (Mandate-12 criterion 3).

RED contract: `des mikado-board` is not a registered `des` subcommand on
master, and `des.cli.mikado_board` / `des.domain.slice_progress_projection`
do not exist yet -- every scenario below fails because the response carries
no `verdict` token, never because of a collection-time import error (P1-P4,
nw-distill-red-scaffolding).
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition import MikadoBoardRenderComposition, RenderResult
from .domain_types import (
    CAUSE_BY_PHRASE,
    SLICE_PLAN_SHAPE_BY_PHRASE,
    DeclaredStatus,
    FeatureId,
)


scenarios("../mikado-board-declared-status-render.feature")


@pytest.fixture
def composition(tmp_path) -> MikadoBoardRenderComposition:
    """Production-wired composition, tmp-rooted."""
    return MikadoBoardRenderComposition(tmp_path)


@pytest.fixture
def result_box() -> dict[str, RenderResult]:
    """Carrier for the render outcome."""
    return {}


def _outcome(result_box: dict[str, RenderResult]) -> RenderResult:
    return result_box["result"]


# --- Background ----------------------------------------------------------


@given("a repository with a feature directory")
def given_repository(composition: MikadoBoardRenderComposition) -> None:
    composition.create_repository()


# --- Given -----------------------------------------------------------------


@given(
    parsers.re(
        r'the Slice Plan for feature "(?P<feature_id>[\w-]+)" declares '
        r'(?P<declarations>.*"(?:pending|shipped)")$'
    )
)
def given_declares_statuses(
    composition: MikadoBoardRenderComposition, feature_id: str, declarations: str
) -> None:
    composition.declare_statuses(FeatureId(feature_id), declarations)


@given(
    parsers.parse(
        'the Slice Plan for feature "{feature_id}" declares {count:d} slices'
        " in document order"
    )
)
def given_declares_many(
    composition: MikadoBoardRenderComposition, feature_id: str, count: int
) -> None:
    composition.declare_many_in_order(FeatureId(feature_id), count)


@given("Ale has already opened the Mikado board for that feature")
def given_already_opened(composition: MikadoBoardRenderComposition) -> None:
    composition.render()


@given(
    parsers.re(
        r"the Slice Plan is edited to declare "
        r'(?P<declarations>.*"(?:pending|shipped)")$'
    )
)
def given_edited_statuses(
    composition: MikadoBoardRenderComposition, declarations: str
) -> None:
    composition.edit_statuses(declarations)


@given(parsers.parse('feature "{feature_id}" has no feature-delta on disk'))
def given_no_feature_delta(
    composition: MikadoBoardRenderComposition, feature_id: str
) -> None:
    composition.omit_feature_delta(FeatureId(feature_id))


@given(parsers.parse('the feature-delta for "{feature_id}" carries {shape}'))
def given_shape(
    composition: MikadoBoardRenderComposition, feature_id: str, shape: str
) -> None:
    composition.provision_shape(
        FeatureId(feature_id), SLICE_PLAN_SHAPE_BY_PHRASE[shape]
    )


# --- When --------------------------------------------------------------------


@when("Ale opens the Mikado board for that feature", target_fixture="result_box")
def when_opens_board(
    composition: MikadoBoardRenderComposition, result_box: dict[str, RenderResult]
) -> dict[str, RenderResult]:
    result_box["result"] = composition.render_tracked()
    return result_box


@when("Ale opens the Mikado board for that feature again", target_fixture="result_box")
def when_opens_board_again(
    composition: MikadoBoardRenderComposition, result_box: dict[str, RenderResult]
) -> dict[str, RenderResult]:
    result_box["result"] = composition.render()
    return result_box


@when("Ale opens the real Mikado board for that feature", target_fixture="result_box")
def when_opens_real_board(
    composition: MikadoBoardRenderComposition, result_box: dict[str, RenderResult]
) -> dict[str, RenderResult]:
    result_box["result"] = composition.render_via_installed_cli()
    return result_box


# --- Then ----------------------------------------------------------------


@then(parsers.re(r'the board shows (?P<declarations>.*"(?:pending|shipped)")$'))
def then_shows_statuses(result_box: dict[str, RenderResult], declarations: str) -> None:
    assert _outcome(result_box).matches_declarations(declarations)


@then(parsers.parse('the board shows exactly one slice, {slice_id}, as "{status}"'))
def then_shows_exactly_one(
    result_box: dict[str, RenderResult], slice_id: str, status: str
) -> None:
    assert _outcome(result_box).is_exactly_one(slice_id, DeclaredStatus(status))


@then(
    parsers.parse(
        "the board shows all {count:d} slices in the same order as the Slice Plan"
    )
)
def then_shows_ordered_run(result_box: dict[str, RenderResult], count: int) -> None:
    assert _outcome(result_box).matches_ordered_run(count)


@then("the shown statuses are read from the Slice Plan itself, not re-derived")
def then_sourced_from_slice_plan(result_box: dict[str, RenderResult]) -> None:
    assert _outcome(result_box).all_sources_are_slice_plan


@then("the render leaves the feature-delta unchanged")
def then_unchanged(composition: MikadoBoardRenderComposition) -> None:
    composition.assert_unchanged()


@then("the board refuses, naming the missing feature-delta as the cause")
def then_refuses_missing_feature_delta(
    result_box: dict[str, RenderResult],
) -> None:
    assert _outcome(result_box).refuses_for_missing_feature_delta


@then("the refusal names how to fix it")
def then_names_how(result_box: dict[str, RenderResult]) -> None:
    assert _outcome(result_box).has_how


@then(parsers.parse("the board refuses, naming {cause} as the cause"))
def then_refuses_naming_cause(result_box: dict[str, RenderResult], cause: str) -> None:
    assert _outcome(result_box).verdict == CAUSE_BY_PHRASE[cause]
