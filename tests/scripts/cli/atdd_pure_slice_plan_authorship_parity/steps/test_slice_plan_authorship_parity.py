"""Step definitions: a DISTILL-originated Slice Plan reads exactly like a
DISCUSS-originated one.

`docs/feature/parallel-by-default-distill-slicing/feature-delta.md` D-1..D-6 /
slice-01.

Layer 3 (subprocess/FS acceptance). Example-only, no PBT machinery
(Mandate 9/11): the three tried combinations (no annotation / dependency
justified / dependency unjustified) form a finite, enumerable closed set,
mirroring the paradigm choice the sibling parallel-by-default-slice-plan
slice-01 AT already made for the same grammar.

The validator has a pure-function contract (it reads a document and returns a
verdict). Every When-step captures the universe first so the Then-step can
assert via `assert_state_delta` that NEITHER fixture was mutated (Mandate 8).

Step bodies delegate to `SlicePlanAuthorshipParityComposition`; no inline
business logic (Mandate-12 criterion 3) -- each body is a typed lookup plus a
composition call.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .composition import ParityResult, SlicePlanAuthorshipParityComposition
from .domain_types import (
    SECOND_ROW_SHAPE_BY_PHRASE,
    VERDICT_BY_PHRASE,
    FeatureId,
)


scenarios("../slice-plan-authorship-parity.feature")


@pytest.fixture
def composition(tmp_path: Path) -> SlicePlanAuthorshipParityComposition:
    """Production-wired composition root over a tmp_path repository."""
    return SlicePlanAuthorshipParityComposition(repo_dir=tmp_path / "repo")


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for the parity result + universe across When -> Then steps."""
    return {}


# --- Given ---------------------------------------------------------------


@given("a feature-delta authored for an atdd_pure feature")
def given_feature(composition: SlicePlanAuthorshipParityComposition) -> None:
    composition.create_feature(FeatureId("parallel-by-default-distill-slicing"))


@given(
    parsers.parse(
        "a DISCUSS-shaped fixture and a DISTILL-shaped fixture whose second "
        "row carries {row_phrase}"
    )
)
def given_fixture_pair(
    composition: SlicePlanAuthorshipParityComposition, row_phrase: str
) -> None:
    composition.provision_pair(SECOND_ROW_SHAPE_BY_PHRASE[row_phrase])


@given(
    parsers.parse(
        "a DISCUSS-shaped fixture and a DISTILL-shaped fixture whose second "
        "row declares {row_phrase}"
    )
)
def given_fixture_pair_declares(
    composition: SlicePlanAuthorshipParityComposition, row_phrase: str
) -> None:
    composition.provision_pair(SECOND_ROW_SHAPE_BY_PHRASE[row_phrase])


# --- When ------------------------------------------------------------------


@when("the acceptance-designer runs the slice-plan check on both fixtures")
def when_run_check_on_both(
    composition: SlicePlanAuthorshipParityComposition,
    result_box: dict[str, object],
) -> None:
    result_box["universe_before"] = composition.capture_universe()
    result_box["result"] = composition.run_check()


# --- Then --------------------------------------------------------------------


@then(parsers.parse("both fixtures are {verdict_phrase}"))
def then_both_fixtures_verdict(
    result_box: dict[str, object], verdict_phrase: str
) -> None:
    result = result_box["result"]
    assert isinstance(result, ParityResult)
    expected = VERDICT_BY_PHRASE[verdict_phrase]
    assert result.discuss.verdict is expected
    assert result.distill.verdict is expected


@then("the two verdicts are identical")
def then_verdicts_identical(result_box: dict[str, object]) -> None:
    """D-2's authorship-blindness claim, expressed directly: the two
    fixtures' (verdict, detail) pairs must be byte-identical."""
    result = result_box["result"]
    assert isinstance(result, ParityResult)
    assert result.verdicts_match, (
        f"authorship divergence detected -- discuss={result.discuss.verdict!r} "
        f"detail={result.discuss.detail!r} vs distill={result.distill.verdict!r} "
        f"detail={result.distill.detail!r}"
    )


@then("both rejections name row 2 as the offending row")
def then_both_rejections_name_offending_row(result_box: dict[str, object]) -> None:
    """GDP-3: the diagnostic names WHAT failed -- the specific row that
    declared a dependency without backing it. This fixture's offending row is
    the second data row under the Slice Plan header (row_no=2 in the per-row
    classifier loop), for BOTH fixture shapes -- the row-number witness never
    shifts because one document happens to carry more headings than the
    other."""
    result = result_box["result"]
    assert isinstance(result, ParityResult)
    assert "row 2" in result.discuss.detail
    assert "row 2" in result.distill.detail
    assert "justification" in result.discuss.detail.lower()
    assert "justification" in result.distill.detail.lower()


@then("the check leaves both feature-deltas unchanged")
def then_both_feature_deltas_unchanged(
    composition: SlicePlanAuthorshipParityComposition,
    result_box: dict[str, object],
) -> None:
    """Pure-function contract: the validator mutates neither fixture
    (Mandate 8)."""
    assert_state_delta(
        before=result_box["universe_before"],  # type: ignore[arg-type]
        after=composition.capture_universe(),
        universe={
            "discuss.exists",
            "discuss.bytes",
            "distill.exists",
            "distill.bytes",
        },
        expected={
            "discuss.exists": unchanged(),
            "discuss.bytes": unchanged(),
            "distill.exists": unchanged(),
            "distill.bytes": unchanged(),
        },
    )
