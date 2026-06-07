"""Step definitions -- slice-01: reuse-first CLI walking skeleton.

F-DESIGN-REUSE-FIRST-GATE-CLI slice-01 (walking skeleton). DDD-1..DDD-7.

Layer 3 (in-process subprocess-equivalent / FS acceptance). Example-only, no
PBT machinery (Mandate 9/11): the walking-skeleton verdict set
(PASS / FAIL / preservation) is a finite enumerable closed set, so
example-based scenarios are the correct paradigm -- the falsifier-gate
forbids PBT on a closed-world finite domain.

The CLI has a pure-function contract (it reads the feature-delta + the
git-diff oracle and emits a verdict). The @then preservation step asserts
via ``assert_state_delta`` over a port-exposed filesystem universe that
neither the feature-delta nor the git-diff oracle is mutated (Mandate 8) --
this is the @contract-shape:unbounded-preservation guarantee.

Step bodies delegate to ``ReuseFirstFixture``; no inline business logic
(Mandate-12 criterion 3) -- each body is a typed lookup plus a composition
call.

RED contract (Mandate 7): on master the production CLI module
``scripts/cli/check_reuse_first_design.py`` does not exist. The crafter
authors a RED scaffold (``__SCAFFOLD__ = True``; ``main`` raises
``AssertionError``) in A_GREEN_ATS so the import resolves and the
invocation raises a semantic ``AssertionError`` (MISSING_FUNCTIONALITY
RED), not a collection-time error. Before the scaffold lands, the
composition.run_check defends with a ModuleNotFoundError->synthetic
UNRECOGNISED_INVOCATION path so the @then assertion fires (RED-for-the
-right-reason at the AT layer); once the scaffold lands the path is
AssertionError->UNRECOGNISED_INVOCATION (still RED-for-the-right-reason);
once the implementation lands the path is the real stdout token -> PASS.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .composition import CheckResult, ReuseFirstFixture
from .domain_types import (
    EXIT_CODE_BY_VERDICT,
    FEATURE_SHAPE_BY_PHRASE,
    VERDICT_BY_PHRASE,
    FeatureId,
    ReuseFirstVerdict,
)


scenarios("../slice-01-reuse-first-cli-walking-skeleton.feature")


# --- Fixtures --------------------------------------------------------------


@pytest.fixture
def composition(tmp_path: Path) -> ReuseFirstFixture:
    """Production-wired composition root over a tmp_path repository."""
    return ReuseFirstFixture(repo_dir=tmp_path / "repo")


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for the CLI result + universe across When -> Then steps."""
    return {}


# --- Background -------------------------------------------------------------


@given("a feature whose design wave has authored a feature-delta")
def given_design_wave_authored_feature_delta(
    composition: ReuseFirstFixture,
) -> None:
    composition.create_feature(FeatureId("reuse-first-cli-demo"))


# --- Given -----------------------------------------------------------------


@given(parsers.parse("the feature carries {shape_phrase}"))
def given_feature_shape(composition: ReuseFirstFixture, shape_phrase: str) -> None:
    composition.provision_feature_shape(FEATURE_SHAPE_BY_PHRASE[shape_phrase])


# --- When ------------------------------------------------------------------


@when("the architect runs the reuse-first check on the feature")
def when_run_reuse_first_check(
    composition: ReuseFirstFixture, result_box: dict[str, object]
) -> None:
    result_box["universe_before"] = composition.capture_universe()
    result_box["result"] = composition.run_check()


# --- Then ------------------------------------------------------------------


@then(parsers.parse("the feature {verdict_phrase}"))
def then_verdict(result_box: dict[str, object], verdict_phrase: str) -> None:
    result = result_box["result"]
    assert isinstance(result, CheckResult)
    expected_verdict = VERDICT_BY_PHRASE[verdict_phrase]
    assert result.verdict is expected_verdict, (
        f"expected verdict {expected_verdict.value}, got {result.verdict.value} "
        f"(exit_code={result.exit_code}, stdout={result.stdout!r}, "
        f"stderr={result.stderr!r})"
    )
    expected_exit = EXIT_CODE_BY_VERDICT[expected_verdict]
    assert result.exit_code == expected_exit, (
        f"expected exit code {expected_exit} for verdict "
        f"{expected_verdict.value}, got {result.exit_code}"
    )


@then("the reuse-first check produced a structured verdict")
def then_structured_verdict_present(result_box: dict[str, object]) -> None:
    """The CLI emitted its single-line stdout token (DDD-4).

    This guards AT3 against fixture-theater: on master the production CLI
    does not exist, so the composition.run_check defends with a synthetic
    UNRECOGNISED_INVOCATION result. AT3's preservation assertion would
    otherwise pass vacuously (no CLI ran, no files mutated). This Then
    step makes AT3 fail-for-the-right-reason on master: the structured
    verdict is absent, the assertion fires, the test is RED.
    """
    result = result_box["result"]
    assert isinstance(result, CheckResult)
    assert result.verdict is not ReuseFirstVerdict.UNRECOGNISED_INVOCATION, (
        f"reuse-first CLI did not produce a structured verdict on stdout "
        f"(exit_code={result.exit_code}, stdout={result.stdout!r}, "
        f"stderr={result.stderr!r}) -- the CLI is absent or the scaffold "
        f"has not yet been replaced with a real implementation"
    )


@then("the reuse-first check leaves the feature-delta and the diff source unchanged")
def then_universe_preserved(
    composition: ReuseFirstFixture, result_box: dict[str, object]
) -> None:
    """Pure-function contract: the CLI mutates no file (Mandate 8).

    @contract-shape:unbounded-preservation -- the universe is the
    feature-delta + git-diff oracle's existence and bytes; both are asserted
    `unchanged` (same existence and same bytes before and after the check).
    """
    assert_state_delta(
        before=result_box["universe_before"],  # type: ignore[arg-type]
        after=composition.capture_universe(),
        universe={
            "feature_delta.exists",
            "feature_delta.bytes",
            "diff_source.exists",
            "diff_source.bytes",
        },
        expected={
            "feature_delta.exists": unchanged(),
            "feature_delta.bytes": unchanged(),
            "diff_source.exists": unchanged(),
            "diff_source.bytes": unchanged(),
        },
    )
