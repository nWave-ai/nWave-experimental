"""Step definitions: the feature-plan validator clears or rejects a Feature Plan.

discuss-epic-mode slice-01 (the `--require-feature-plan` walking skeleton).

Layer 3 (subprocess/FS acceptance). Example-only, no PBT machinery
(Mandate 9/11): the Feature Plan shapes form a finite, enumerable closed set
(well-formed / section-absent / four-columns / columns-reordered), so a
`Scenario` + `Scenario Outline` over the closed set is the correct paradigm --
the falsifier-gate forbids PBT on a closed-world finite domain.

The validator has a pure-function contract (it reads the epic-delta and returns
a verdict). The Then-step asserts via `assert_state_delta` over a port-exposed
filesystem universe that the epic-delta is NOT mutated (Mandate 8).

Step bodies delegate to `FeaturePlanValidationComposition`; no inline business
logic (Mandate-12 criterion 3) -- each body is a typed lookup plus a composition
call.

Active-RED contract (atdd_pure): every feature-plan assertion FAILS on the
current tip and PASSES once slice-01 lands. The `--require-feature-plan` flag is
unknown today; invoked with it, `main` prints usage and returns exit 1, emitting
no JSON `verdict` line -- so the verdict reads as `UNRECOGNISED_INVOCATION`, a
deliberate missing-functionality RED (wrong verdict), not a test bug. The module
imports cleanly (it exists today), so the RED is a semantic AssertionError, never
a collection / import error.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .composition import FeaturePlanValidationComposition, ValidationResult
from .domain_types import (
    FEATURE_PLAN_SHAPE_BY_PHRASE,
    VERDICT_BY_PHRASE,
    EpicId,
)


scenarios("../feature-plan-validation.feature")


@pytest.fixture
def composition(tmp_path: Path) -> FeaturePlanValidationComposition:
    """Production-wired composition root over a tmp_path repository."""
    return FeaturePlanValidationComposition(repo_dir=tmp_path / "repo")


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for the validation result + universe across When -> Then steps."""
    return {}


# --- Given -------------------------------------------------------------------


@given("an epic-delta authored for a multi-feature epic")
def given_epic(composition: FeaturePlanValidationComposition) -> None:
    composition.create_epic(EpicId("flow-v2-wave-migrations"))


@given(parsers.parse("the epic-delta carries {feature_plan}"))
def given_feature_plan(
    composition: FeaturePlanValidationComposition, feature_plan: str
) -> None:
    composition.provision_epic_delta(FEATURE_PLAN_SHAPE_BY_PHRASE[feature_plan])


# --- When --------------------------------------------------------------------


@when("the maintainer runs the feature-plan check on the epic-delta")
def when_run_feature_plan_check(
    composition: FeaturePlanValidationComposition,
    result_box: dict[str, object],
) -> None:
    result_box["universe_before"] = composition.capture_universe()
    result_box["result"] = composition.run_feature_plan_check()


# --- Then --------------------------------------------------------------------


@then(parsers.parse("the Feature Plan is {verdict_phrase}"))
def then_verdict(result_box: dict[str, object], verdict_phrase: str) -> None:
    result = result_box["result"]
    assert isinstance(result, ValidationResult)
    assert result.verdict is VERDICT_BY_PHRASE[verdict_phrase]


@then("the check leaves the epic-delta unchanged")
def then_epic_delta_unchanged(
    composition: FeaturePlanValidationComposition,
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
