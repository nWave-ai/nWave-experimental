"""Step definitions -- slice-01: design-dimension coverage CLI walking skeleton.

F-OSS-UPSTREAM-WAVE-GATE-PAIRS pair-1 (DESIGN-dimensions <-> DISTILL-pbt),
slice-01 (existence-join walking skeleton).

Layer 3 (in-process subprocess-equivalent / FS acceptance). Example-only, no
PBT machinery (Mandate 9/11): the walking-skeleton verdict set
(PASS / INDETERMINATE / MALFORMED) is a finite enumerable closed set, so
example-based scenarios are the correct paradigm -- the falsifier-gate forbids
PBT on a closed-world finite domain. (The unbounded input-axes -- arbitrary
feature-delta text, arbitrary carrier-comment placement -- are the layer-1
parser unit scope, PBT territory authored by DELIVER, not at this layer-3 AT.)

The CLI has a bounded-change contract (it reads the feature-delta + the AT
corpus and emits a verdict; it writes ONLY stdout/stderr + exit code). The
@then preservation step asserts via ``assert_state_delta`` over a port-exposed
filesystem universe that neither the feature-delta nor the carrier file is
mutated (Mandate 8) -- this is the @contract-shape:unbounded-preservation
guarantee (DIM-10 tree-safe half).

Step bodies delegate to ``DimensionCoverageFixture``; no inline business logic
(Mandate-12 criterion 3) -- each body is a typed lookup plus a composition
call.

RED contract (Mandate 7): on master the production CLI module
``scripts/cli/check_design_dimension_coverage.py`` does not exist. The crafter
authors a RED scaffold (``__SCAFFOLD__ = True``; ``main`` raises
``AssertionError``) in A_GREEN_ATS so the import resolves and the invocation
raises a semantic ``AssertionError`` (MISSING_FUNCTIONALITY RED), not a
collection-time error. Before the scaffold lands, the composition.run_check
defends with a ModuleNotFoundError->synthetic UNRECOGNISED_INVOCATION path so
the @then assertion fires (RED-for-the-right-reason at the AT layer); once the
scaffold lands the path is AssertionError->UNRECOGNISED_INVOCATION (still
RED-for-the-right-reason); once the implementation lands the path is the real
stdout token -> PASS / INDETERMINATE / MALFORMED.

Driving-port-only (Mandate-13): the gate is exercised exclusively through its
``main(argv)`` CLI entry point inside the composition fixture -- NO
direct-domain import of the dimensions-block parser or carrier-comment parser.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from tests.common.state_delta import assert_state_delta, unchanged

from .composition import CheckResult, DimensionCoverageFixture
from .domain_types import (
    CORPUS_SHAPE_BY_PHRASE,
    EXIT_CODE_BY_VERDICT,
    VERDICT_BY_PHRASE,
    DimensionCoverageVerdict,
    FeatureId,
)


scenarios("../slice-01-design-dimension-coverage-walking-skeleton.feature")


# --- Fixtures --------------------------------------------------------------


@pytest.fixture
def composition(tmp_path: Path) -> DimensionCoverageFixture:
    """Production-wired composition root over a tmp_path repository."""
    return DimensionCoverageFixture(repo_dir=tmp_path / "repo")


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for the CLI result + universe across When -> Then steps."""
    return {}


# --- Background -------------------------------------------------------------


@given("a feature whose design wave has declared a dimensions block")
def given_design_wave_declared_dimensions_block(
    composition: DimensionCoverageFixture,
) -> None:
    composition.create_feature(FeatureId("design-dimension-coverage-demo"))


# --- Given -----------------------------------------------------------------


@given(parsers.parse("the feature has {corpus_shape_phrase}"))
def given_feature_corpus_shape(
    composition: DimensionCoverageFixture, corpus_shape_phrase: str
) -> None:
    composition.provision_corpus_shape(CORPUS_SHAPE_BY_PHRASE[corpus_shape_phrase])


# --- When ------------------------------------------------------------------


@when("the acceptance designer runs the design-dimension coverage check on the feature")
def when_run_coverage_check(
    composition: DimensionCoverageFixture, result_box: dict[str, object]
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


@then("the coverage check produced a structured verdict")
def then_structured_verdict_present(result_box: dict[str, object]) -> None:
    """The CLI emitted its single-line stdout token (the Gate Contract surface).

    This guards the preservation scenario against fixture-theater: on master
    the production CLI does not exist, so composition.run_check defends with a
    synthetic UNRECOGNISED_INVOCATION result. The preservation assertion would
    otherwise pass vacuously (no CLI ran, no files mutated). This Then step
    makes the scenario fail-for-the-right-reason on master: the structured
    verdict is absent, the assertion fires, the test is RED.
    """
    result = result_box["result"]
    assert isinstance(result, CheckResult)
    assert result.verdict is not DimensionCoverageVerdict.UNRECOGNISED_INVOCATION, (
        f"design-dimension coverage CLI did not produce a structured verdict on "
        f"stdout (exit_code={result.exit_code}, stdout={result.stdout!r}, "
        f"stderr={result.stderr!r}) -- the CLI is absent or the scaffold has "
        f"not yet been replaced with a real implementation"
    )


@then("the coverage check leaves the feature-delta and the corpus unchanged")
def then_universe_preserved(
    composition: DimensionCoverageFixture, result_box: dict[str, object]
) -> None:
    """Bounded-change contract: the CLI mutates no file (Mandate 8).

    @contract-shape:unbounded-preservation -- the universe is the
    feature-delta + the AT-corpus carrier file's existence and bytes; both are
    asserted ``unchanged`` (same existence and same bytes before and after the
    check). This pins the DIM-10 tree-safe invariant at the walking-skeleton
    layer: the gate is a reader, never a writer of the inputs it inspects.
    """
    assert_state_delta(
        before=result_box["universe_before"],  # type: ignore[arg-type]
        after=composition.capture_universe(),
        universe={
            "feature_delta.exists",
            "feature_delta.bytes",
            "carrier_file.exists",
            "carrier_file.bytes",
        },
        expected={
            "feature_delta.exists": unchanged(),
            "feature_delta.bytes": unchanged(),
            "carrier_file.exists": unchanged(),
            "carrier_file.bytes": unchanged(),
        },
    )
