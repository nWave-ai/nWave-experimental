"""Step definitions -- slice-02: design-dimension coverage report granularity.

F-OSS-UPSTREAM-WAVE-GATE-PAIRS pair-1 (DESIGN-dimensions <-> DISTILL-pbt),
slice-02 (report granularity + column-1 non-vacuity: DIM-4, DIM-6, DIM-7).

slice-01 shipped the bare verdict surface (PASS / INDETERMINATE / MALFORMED).
slice-02 specifies the REPORT GRANULARITY on top of that bare verdict:

  - DIM-4: when a dimension is flagged unwitnessed, the report resolves the
    dimension-ID to its summary text (``DIM-N (summary)``), never the bare
    ``DIM-N``. The summary is the comprehension-key the acceptance designer
    reads to know WHICH behavior axis is uncovered.
  - DIM-6: a dimension-ID mentioned only in a prose / rationale cell does NOT
    satisfy the join (column-1 read only); the dimension stays unwitnessed and
    the report still resolves its summary -- the prose mention is non-vacuous.
  - DIM-7: a dimensions block whose only rows carry a blank / non-DIM column-1
    is MALFORMED (never a silent zero-dimensions PASS), and the report names
    the column-1 vacuity reason, not an undifferentiated either/or.

Layer 3 (in-process subprocess-equivalent / FS acceptance). Example-only, no
PBT machinery (Mandate 9/11): the report-granularity observables are a finite
enumerable closed set of operator-facing report tokens; the falsifier-gate
forbids PBT on a closed-world finite domain.

The CLI has a bounded-change contract (it reads the feature-delta + the AT
corpus and emits a report; it writes ONLY stdout/stderr + exit code). Each
scenario re-asserts the preservation guard via ``assert_state_delta`` over the
port-exposed filesystem universe (Mandate 8, @contract-shape:unbounded-
preservation) -- the report surface is observable, the inputs are never
mutated.

Step bodies delegate to ``DimensionCoverageFixture`` + the typed slice-02
lookups; no inline business logic (Mandate-12 criterion 3). The Background
``@given`` is the SAME step as slice-01 -- it is IMPORTED here (shared-import
re-use, an explicitly S1-tolerable variant: one function object, one
registration, no shadow), never re-declared with its own body.

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
    SLICE_02_CORPUS_SHAPE_BY_PHRASE,
    UNWITNESSED_DIMENSION_ID,
    UNWITNESSED_DIMENSION_SUMMARY,
    DimensionCoverageVerdict,
    FeatureId,
)


scenarios("../slice-02-design-dimension-coverage-report-granularity.feature")


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


@given("a feature whose design wave has declared a dimensions block for its report")
def given_design_wave_declared_dimensions_block_for_report(
    composition: DimensionCoverageFixture,
) -> None:
    """Slice-02 Background -- distinct literal text from slice-01 (S1-unique).

    Delegates to the SAME composition method as slice-01's Background; the step
    LITERAL differs so the two step files share zero literal-arg strings (S1
    step-text uniqueness within the feature dir).
    """
    composition.create_feature(FeatureId("design-dimension-coverage-demo"))


# --- Given -----------------------------------------------------------------


@given(parsers.parse("the design wave declared {corpus_shape_phrase}"))
def given_slice_02_corpus_shape(
    composition: DimensionCoverageFixture, corpus_shape_phrase: str
) -> None:
    composition.provision_corpus_shape(
        SLICE_02_CORPUS_SHAPE_BY_PHRASE[corpus_shape_phrase]
    )


# --- When ------------------------------------------------------------------


@when(
    "the acceptance designer runs the design-dimension coverage report on the feature"
)
def when_run_coverage_report(
    composition: DimensionCoverageFixture, result_box: dict[str, object]
) -> None:
    result_box["universe_before"] = composition.capture_universe()
    result_box["result"] = composition.run_check()


# --- Then ------------------------------------------------------------------


@then("the report names the uncovered dimension by its summary text")
def then_report_resolves_summary(result_box: dict[str, object]) -> None:
    """DIM-4 / DIM-6: the report resolves the dimension-ID to its summary text.

    The comprehension-key contract: an operator reading the report sees the
    summary describing WHICH behavior axis is uncovered, not the opaque
    identifier. On the shipped slice-01 CLI the INDETERMINATE report emits the
    bare ``DIM-N`` only, so this assertion fires -- RED-for-the-right-reason
    (the slice-02 report-granularity surface is absent), not a collection error.
    """
    result = result_box["result"]
    assert isinstance(result, CheckResult)
    assert result.verdict is DimensionCoverageVerdict.INDETERMINATE, (
        f"expected the uncovered dimension to be flagged INDETERMINATE, got "
        f"{result.verdict.value} (exit_code={result.exit_code}, "
        f"stdout={result.stdout!r}, stderr={result.stderr!r})"
    )
    assert UNWITNESSED_DIMENSION_SUMMARY in result.report, (
        f"the design-dimension coverage report does not name the uncovered "
        f"dimension by its summary text {UNWITNESSED_DIMENSION_SUMMARY!r} -- it "
        f"resolves the bare identifier only, so the acceptance designer cannot "
        f"read WHICH behavior axis is uncovered (report={result.report!r})"
    )


@then("the report does not name the uncovered dimension by its bare identifier alone")
def then_report_not_bare_identifier(result_box: dict[str, object]) -> None:
    """DIM-4: the identifier never appears WITHOUT its summary text.

    A report carrying ``DIM-OVERSIZE`` with no adjacent summary is the
    comprehension-failure slice-02 forbids. The contract is satisfied when the
    summary text accompanies the identifier; this step pins that the bare
    identifier is never the SOLE token naming the dimension. On the shipped CLI
    the report carries the bare identifier with no summary, so this fires RED.
    """
    result = result_box["result"]
    assert isinstance(result, CheckResult)
    identifier_present = UNWITNESSED_DIMENSION_ID in result.report
    summary_present = UNWITNESSED_DIMENSION_SUMMARY in result.report
    assert not (identifier_present and not summary_present), (
        f"the design-dimension coverage report names the uncovered dimension "
        f"by its bare identifier {UNWITNESSED_DIMENSION_ID!r} with no "
        f"accompanying summary text -- the operator sees an opaque identifier, "
        f"not WHICH behavior axis is uncovered (report={result.report!r})"
    )


@then("the feature is reported malformed because its identifier column is vacuous")
def then_report_names_vacuous_identifier_column(
    result_box: dict[str, object],
) -> None:
    """DIM-7: MALFORMED report names the column-1 vacuity reason.

    A block whose only rows carry a blank / non-DIM column-1 is MALFORMED
    (never a silent zero-dimensions PASS). The report must DISTINGUISH this from
    an absent corpus by naming the identifier-column vacuity. On the shipped CLI
    the MALFORMED report is an undifferentiated "no parseable block OR absent
    corpus", so the column-1-vacuity reason is absent -> RED.
    """
    result = result_box["result"]
    assert isinstance(result, CheckResult)
    assert result.verdict is DimensionCoverageVerdict.MALFORMED, (
        f"expected a block with a vacuous identifier column to be reported "
        f"MALFORMED, got {result.verdict.value} (exit_code={result.exit_code}, "
        f"stdout={result.stdout!r}, stderr={result.stderr!r})"
    )
    report_lower = result.report.lower()
    assert "identifier column" in report_lower or "column-1" in report_lower, (
        f"the MALFORMED report does not name WHY the block is malformed (the "
        f"identifier column is vacuous) -- it emits an undifferentiated "
        f"either/or, so the acceptance designer cannot tell a vacuous "
        f"identifier column from an absent corpus (report={result.report!r})"
    )


@then(
    "running the design-dimension coverage report leaves the feature-delta and the corpus unchanged"
)
def then_report_universe_preserved(
    composition: DimensionCoverageFixture, result_box: dict[str, object]
) -> None:
    """Bounded-change contract: the report mutates no file (Mandate 8).

    @contract-shape:unbounded-preservation -- the universe is the feature-delta
    + the AT-corpus carrier file's existence and bytes; both asserted
    ``unchanged``. The report surface is observable; the inputs the gate
    inspects are never written (DIM-10 tree-safe invariant carried forward).
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
