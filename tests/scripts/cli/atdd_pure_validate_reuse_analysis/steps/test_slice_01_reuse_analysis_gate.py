"""Step definitions: the Reuse Analysis gate clears or rejects a reuse table.

F-DESIGN-REUSE-FIRST-GATE slice-01 (walking skeleton). DDD-1..DDD-11.

Layer 3 (subprocess/FS acceptance). Example-only, no PBT machinery
(Mandate 9/11): the Reuse Analysis shapes form a finite enumerable closed set
(well-formed / section-absent / this-feature-gold), so example-based scenarios
are the correct paradigm -- the falsifier-gate forbids PBT on a closed-world
finite domain.

The validator has a pure-function contract (it reads the feature-delta and
returns a verdict). The When-step asserts via `assert_state_delta` over a
port-exposed filesystem universe that the feature-delta is NOT mutated
(Mandate 8) -- this is the @contract-shape:unbounded-preservation guarantee.

Step bodies delegate to `ReuseAnalysisComposition`; no inline business logic
(Mandate-12 criterion 3) -- each body is a typed lookup plus a composition
call.

RED contract (Mandate 7): every Reuse Analysis assertion FAILS on master and
PASSES once slice-01 lands. On master `validate_feature_delta` carries a
`validate_reuse_analysis_content` RED scaffold raising `AssertionError`;
invoking the CLI in --require-reuse-analysis mode propagates that semantic
`AssertionError` (MISSING_FUNCTIONALITY RED). The import resolves cleanly --
the scaffold symbols exist today -- so the RED signal is missing
functionality, never a collection error.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .composition import ReuseAnalysisComposition, ValidationResult
from .domain_types import (
    CHECK_MODE_BY_PHRASE,
    REUSE_TABLE_SHAPE_BY_PHRASE,
    VERDICT_BY_PHRASE,
    FeatureId,
)


scenarios("../slice-01-reuse-analysis-gate.feature")


@pytest.fixture
def composition(tmp_path: Path) -> ReuseAnalysisComposition:
    """Production-wired composition root over a tmp_path repository."""
    return ReuseAnalysisComposition(repo_dir=tmp_path / "repo")


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for the validation result + universe across When -> Then steps."""
    return {}


# --- Given -------------------------------------------------------------------


@given("a feature-delta authored for a code feature")
def given_feature(composition: ReuseAnalysisComposition) -> None:
    composition.create_feature(FeatureId("reuse-gate-demo"))


@given(parsers.parse("the feature-delta carries {table_shape}"))
def given_reuse_table(composition: ReuseAnalysisComposition, table_shape: str) -> None:
    composition.provision_feature_delta(REUSE_TABLE_SHAPE_BY_PHRASE[table_shape])


# --- When --------------------------------------------------------------------


@when(parsers.parse("the architect runs {check_mode} on the feature-delta"))
def when_run_check(
    composition: ReuseAnalysisComposition,
    result_box: dict[str, object],
    check_mode: str,
) -> None:
    result_box["universe_before"] = composition.capture_universe()
    result_box["result"] = composition.run_check(CHECK_MODE_BY_PHRASE[check_mode])


# --- Then --------------------------------------------------------------------


@then(parsers.parse("the Reuse Analysis is {verdict_phrase}"))
def then_verdict(result_box: dict[str, object], verdict_phrase: str) -> None:
    result = result_box["result"]
    assert isinstance(result, ValidationResult)
    assert result.verdict is VERDICT_BY_PHRASE[verdict_phrase]


@then("the check leaves the feature-delta unchanged")
def then_feature_delta_unchanged(
    composition: ReuseAnalysisComposition,
    result_box: dict[str, object],
) -> None:
    """Pure-function contract: the validator mutates no file (Mandate 8).

    @contract-shape:unbounded-preservation -- the universe is the
    feature-delta's existence and bytes; both are asserted `unchanged` (same
    existence and same bytes before and after the check).
    """
    assert_state_delta(
        before=result_box["universe_before"],  # type: ignore[arg-type]
        after=composition.capture_universe(),
        universe={"feature_delta.exists", "feature_delta.bytes"},
        expected={
            "feature_delta.exists": unchanged(),
            "feature_delta.bytes": unchanged(),
        },
    )
