"""Step definitions: the feature-plan validator rejects an infrastructure-only epic.

discuss-epic-mode slice-03 (the feature-granularity cohesion-MECC witness).

Layer 3 (subprocess/FS acceptance). Example-only, no PBT machinery
(Mandate 9/11): the cohesion shapes form a finite, enumerable closed set
(all-infrastructure / one-value-bearing / single-infrastructure), so a
`Scenario` over the closed set is the correct paradigm -- the falsifier-gate
forbids PBT on a closed-world finite domain.

The validator has a pure-function contract (it reads the epic-delta and returns a
verdict). The Then-step asserts via `assert_state_delta` over a port-exposed
filesystem universe that the epic-delta is NOT mutated (Mandate 8).

Step bodies delegate to `FeatureCohesionComposition`; no inline business logic
(Mandate-12 criterion 3) -- each body is a typed lookup plus a composition call,
or a single observation + assertion.

WITNESS-GREEN contract (atdd_pure, HONEST): every cohesion assertion PASSES on the
current tip -- the slice-03 behaviour pre-landed in slice-01's generic-core
refactor (commit e4e5e6b02), which calls `_classify_slice_cohesion(rows,
spec.row_noun)` for both plan modes with the feature spec's `row_noun="feature"`.
This suite is the WITNESS for an already-wired-but-unwitnessed seam (the inverse
of a dormant seam: wired, reached from the real entry point, but uncovered by any
AT). Fabricating a RED against correct production would be the false-RED /
Fixture-Theater anti-pattern. The escalation + reasoning is in the slice-03
red-classification doc.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .composition import CohesionResult, FeatureCohesionComposition
from .domain_types import (
    COHESION_SHAPE_BY_PHRASE,
    CohesionVerdict,
    EpicId,
)


scenarios("../feature-cohesion-validation.feature")


@pytest.fixture
def composition(tmp_path: Path) -> FeatureCohesionComposition:
    """Production-wired composition root over a tmp_path repository."""
    return FeatureCohesionComposition(repo_dir=tmp_path / "repo")


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for the validation result + universe across When -> Then steps."""
    return {}


# --- Given -------------------------------------------------------------------


@given("an epic decomposed into a Feature Plan")
def given_epic(composition: FeatureCohesionComposition) -> None:
    composition.create_epic(EpicId("flow-v2-wave-migrations"))


@given(parsers.parse("the epic-delta carries {cohesion_shape}"))
def given_cohesion_shape(
    composition: FeatureCohesionComposition, cohesion_shape: str
) -> None:
    composition.provision_epic_delta(COHESION_SHAPE_BY_PHRASE[cohesion_shape])


# --- When --------------------------------------------------------------------


@when("the maintainer runs the cohesion check on the epic")
def when_run_feature_plan_check(
    composition: FeatureCohesionComposition,
    result_box: dict[str, object],
) -> None:
    result_box["universe_before"] = composition.capture_universe()
    result_box["result"] = composition.run_feature_plan_check()


# --- Then --------------------------------------------------------------------


def _result(result_box: dict[str, object]) -> CohesionResult:
    """Typed accessor for the carried CohesionResult (keeps Then bodies lean)."""
    result = result_box["result"]
    assert isinstance(result, CohesionResult)
    return result


@then("the epic is rejected as infrastructure-only")
def then_rejected_infra_only(result_box: dict[str, object]) -> None:
    assert _result(result_box).verdict is CohesionVerdict.REJECTED_INFRA_ONLY
    assert _result(result_box).exit_code == 1


@then("the rejection names the cause in feature terms")
def then_names_cause_in_feature_terms(result_box: dict[str, object]) -> None:
    assert _result(result_box).names_cause_in_feature_terms


@then("the epic clears the cohesion floor")
def then_clears_floor(result_box: dict[str, object]) -> None:
    assert _result(result_box).verdict is CohesionVerdict.CLEARS_FLOOR
    assert _result(result_box).exit_code == 0


@then("the cohesion check leaves the epic-delta unchanged")
def then_epic_delta_unchanged(
    composition: FeatureCohesionComposition,
    result_box: dict[str, object],
) -> None:
    """Pure-function contract: the validator mutates no file (Mandate 8).

    The universe is the epic-delta's existence and bytes; both are asserted
    `unchanged` -- same existence and same bytes before and after the check.
    """
    assert_state_delta(
        before=result_box["universe_before"],  # type: ignore[arg-type]
        after=composition.capture_universe(),
        universe={"epic_delta.exists", "epic_delta.bytes"},
        expected={
            "epic_delta.exists": unchanged(),
            "epic_delta.bytes": unchanged(),
        },
    )
