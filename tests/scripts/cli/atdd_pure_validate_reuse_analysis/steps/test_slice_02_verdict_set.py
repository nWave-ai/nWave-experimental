"""Step definitions: the Reuse Analysis gate's full closed verdict set.

F-DESIGN-REUSE-FIRST-GATE slice-02 (PARKED -- moved into the collected tests/
tree by the DELIVER loop when slice-02 is delivered). DDD-2, DDD-3, DDD-7,
DDD-9, DDD-11.

Layer 3 (subprocess/FS acceptance). Example-only, no PBT machinery
(Mandate 9/11): the malformed / unjustified / accepted verdicts and the DDD-7
normalization universe form a finite enumerable closed set, so a
`Scenario Outline` over the closed set is the correct paradigm -- the
falsifier-gate forbids PBT on a closed-world finite domain.

The validator has a pure-function contract; the When-step asserts via
`assert_state_delta` over a port-exposed filesystem universe that the
feature-delta is NOT mutated (Mandate 8).

Step bodies delegate to `ReuseAnalysisComposition`; no inline business logic
(Mandate-12 criterion 3). The step-method vocabulary is SHARED verbatim with
slice-01 -- `given_feature`, `given_reuse_table`, `when_run_check`,
`then_verdict`, `then_feature_delta_unchanged` are the same names; only the
`.feature` scenarios differ.

RED contract (Mandate 7): identical to slice-01 -- on master
`validate_reuse_analysis_content` is a RED scaffold raising `AssertionError`,
so every assertion FAILS with a semantic `AssertionError`
(MISSING_FUNCTIONALITY RED) and PASSES once the slice-02 crafter implements
the full verdict set.
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


scenarios("../slice-02-verdict-set.feature")


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
    """Pure-function contract: the validator mutates no file (Mandate 8)."""
    assert_state_delta(
        before=result_box["universe_before"],  # type: ignore[arg-type]
        after=composition.capture_universe(),
        universe={"feature_delta.exists", "feature_delta.bytes"},
        expected={
            "feature_delta.exists": unchanged(),
            "feature_delta.bytes": unchanged(),
        },
    )
