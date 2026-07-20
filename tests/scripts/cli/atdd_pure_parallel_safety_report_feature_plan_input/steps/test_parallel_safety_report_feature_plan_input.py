"""Step definitions: a maintainer gets a MEASURED verdict between two features
an epic declares parallel.

`docs/feature/parallel-by-default-feature-plan/feature-delta.md` D-6/D-7 /
slice-02.

Layer 3 (subprocess/FS acceptance, in-process CLI + real `des blast-radius`
subprocess underneath). Example-only (Mandate 9/11): the input-source and
declared-serial-scope malformed shapes form a finite, enumerable closed set,
so a `Scenario Outline` covers CT-8's two cases.

The report has a read-only contract (Effect Isolation). Every When-step
captures the universe first so the Then-step can assert via
`assert_state_delta` that the epic-delta was NOT mutated (Mandate 8).

Step bodies delegate to `ParallelSafetyReportFeaturePlanComposition`; no
inline business logic (Mandate-12 criterion 3) -- each body is a typed lookup
plus a composition call.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .composition import ParallelSafetyReportFeaturePlanComposition, ReportResult
from .domain_types import (
    INPUT_SOURCE_CASE_BY_PHRASE,
    OUTCOME_BY_PHRASE,
    EpicId,
    FeatureId,
    MeasurementFixture,
)


scenarios("../parallel-safety-report-feature-plan-input.feature")


@pytest.fixture
def composition(tmp_path: Path) -> ParallelSafetyReportFeaturePlanComposition:
    """Production-wired composition root over a tmp_path repository."""
    return ParallelSafetyReportFeaturePlanComposition(repo_dir=tmp_path / "repo")


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for the report result + universe across When -> Then steps."""
    return {}


# --- Given -----------------------------------------------------------------


@given("an epic-delta authored for a multi-feature epic")
def given_epic(composition: ParallelSafetyReportFeaturePlanComposition) -> None:
    composition.create_epic(EpicId("swarm-parallel-delivery"))


@given(
    "the epic-delta carries a Feature Plan declaring feature-a and feature-b "
    "parallel-safe and feature-c depends-on feature-b"
)
def given_feature_plan(composition: ParallelSafetyReportFeaturePlanComposition) -> None:
    composition.provision_feature_plan()


@given("the repository's feature-a and feature-b touch disjoint files")
def given_disjoint_repo(
    composition: ParallelSafetyReportFeaturePlanComposition,
) -> None:
    composition.provision_repository_fixture(MeasurementFixture.DISJOINT)


@given("the repository's feature-a and feature-b touch an overlapping file")
def given_overlapping_repo(
    composition: ParallelSafetyReportFeaturePlanComposition,
) -> None:
    composition.provision_repository_fixture(MeasurementFixture.OVERLAPPING)


@given("the repository's feature-a scope cannot be measured within the time budget")
def given_timed_out_repo(
    composition: ParallelSafetyReportFeaturePlanComposition,
) -> None:
    composition.provision_repository_fixture(MeasurementFixture.TIMED_OUT)


# --- When --------------------------------------------------------------------


@when(
    parsers.parse(
        "the maintainer runs the parallel-safety report over the epic-delta "
        "for {feature_a} and {feature_b}"
    )
)
def when_run_report(
    composition: ParallelSafetyReportFeaturePlanComposition,
    result_box: dict[str, object],
    feature_a: str,
    feature_b: str,
) -> None:
    result_box["universe_before"] = composition.capture_universe()
    result_box["result"] = composition.run_measurement_report(
        (FeatureId(feature_a), FeatureId(feature_b)), forced_timeout=False
    )


@when(
    parsers.parse(
        "the maintainer runs the parallel-safety report over the epic-delta "
        "for {feature_a} and {feature_b} with a forced timeout"
    )
)
def when_run_report_forced_timeout(
    composition: ParallelSafetyReportFeaturePlanComposition,
    result_box: dict[str, object],
    feature_a: str,
    feature_b: str,
) -> None:
    result_box["universe_before"] = composition.capture_universe()
    result_box["result"] = composition.run_measurement_report(
        (FeatureId(feature_a), FeatureId(feature_b)), forced_timeout=True
    )


@when(
    parsers.parse(
        "the maintainer runs the parallel-safety report with {input_source_case}"
    )
)
def when_run_report_input_source_case(
    composition: ParallelSafetyReportFeaturePlanComposition,
    result_box: dict[str, object],
    input_source_case: str,
) -> None:
    result_box["universe_before"] = composition.capture_universe()
    result_box["result"] = composition.run_report_with_input_source_case(
        INPUT_SOURCE_CASE_BY_PHRASE[input_source_case]
    )


# --- Then ----------------------------------------------------------------------


@then(parsers.parse("the report measures the pair {outcome_phrase}"))
def then_report_outcome(result_box: dict[str, object], outcome_phrase: str) -> None:
    result = result_box["result"]
    assert isinstance(result, ReportResult)
    assert result.outcome is OUTCOME_BY_PHRASE[outcome_phrase]


@then("the report event shape matches the feature-delta input path")
def then_event_shape_matches(result_box: dict[str, object]) -> None:
    """CT-7: `--epic-delta` emits the SAME JSON event shape as `--feature-delta`
    (D-6) -- no new/renamed top-level key introduced for the feature-
    granularity input source."""
    result = result_box["result"]
    assert isinstance(result, ReportResult)
    assert set(result.payload.keys()) == {
        "event",
        "verdict",
        "pair",
        "overlap",
        "reasons",
    }


@then("the report measures the pair DRIFT naming the overlapping file")
def then_drift_names_overlap(result_box: dict[str, object]) -> None:
    result = result_box["result"]
    assert isinstance(result, ReportResult)
    assert "shared/index_schema.py" in result.payload["overlap"]["files"], (
        "DRIFT must name the file both features touched (Domain Example 5)"
    )


@then("the report measures the pair UNMEASURED naming the unmeasurable file")
def then_unmeasured_names_file(result_box: dict[str, object]) -> None:
    result = result_box["result"]
    assert isinstance(result, ReportResult)
    unmeasured = result.payload["unmeasured"]
    assert unmeasured["slice"] == "feature-a"
    assert "des/config.py" in unmeasured["paths"]


@then(
    "the report rejects the invocation naming feature-c as not a declared-"
    "parallel Feature Plan row"
)
def then_rejects_declared_serial_scope(result_box: dict[str, object]) -> None:
    from .domain_types import ReportOutcome

    result = result_box["result"]
    assert isinstance(result, ReportResult)
    assert result.outcome is ReportOutcome.INPUT_REJECTED
    reasons_text = " ".join(str(r) for r in result.payload["reasons"])
    assert "feature-c" in reasons_text, "must name the offending feature row"
    assert "Feature Plan row" in reasons_text, (
        "the rejection noun must read 'Feature Plan row' (feature-granularity), "
        "never 'Slice Plan row' -- D-6/DC/DD"
    )


@then("the report rejects the invocation for an ambiguous input source")
def then_rejects_ambiguous_input_source(result_box: dict[str, object]) -> None:
    from .domain_types import ReportOutcome

    result = result_box["result"]
    assert isinstance(result, ReportResult)
    assert result.exit_code == 2
    assert result.outcome is ReportOutcome.INPUT_REJECTED
    assert result.payload["reasons"], "a rejection must self-explain WHY (>=1 reason)"


@then("the check leaves the epic-delta unchanged")
def then_epic_delta_unchanged(
    composition: ParallelSafetyReportFeaturePlanComposition,
    result_box: dict[str, object],
) -> None:
    """Read-only contract: the report mutates no file (Mandate 8, Effect
    Isolation, DESIGN [REF] Driving Ports)."""
    assert_state_delta(
        before=result_box["universe_before"],  # type: ignore[arg-type]
        after=composition.capture_universe(),
        universe={"document.exists", "document.bytes"},
        expected={
            "document.exists": unchanged(),
            "document.bytes": unchanged(),
        },
    )
