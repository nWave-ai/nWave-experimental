"""Step definitions for slice-04 -- the cycle's REAL coverage-map verify leg.

slice-04 of oss-feature-end-emit-cli (option (b) RATIFIED, Ale 2026-06-03;
OQ-3=(i) -- mechanism-complete = R2 closed).

Step bodies are delegate-only (Mandate-12 criterion 3): each is a single
``FeatureEndCoverageMapComposition`` call + one observable assertion. All
orchestration logic lives in the production ``des feature-end run`` subcommand (a
thin shim over the platform-agnostic feature-end-cycle use-case that, in
slice-04, RUNS the ported §5.3 coverage-map verify core in-process and emits the
2 coverage-map records iff the verify passes). The composition root only wires
the real subprocess, stages the passing gate ENVIRONMENT plus the coverage-map
artifact (signed / unsigned / stale -- never an injected verdict), reads the
coverage-map records back through the production ``AtCompletionLedger`` reader
(the audit substrate ``des verify-integrity`` consumes), and feeds the post-cycle
ledger to the real ``des verify-integrity`` consumer to pin the fully-reconciled
boundary.

DIVERGENCE PAIR: the Given steps stage the coverage-map ARTIFACT (a genuinely
human-signed map, or an unsigned `_pending_` map, or a stale-digest map), NOT a
verdict. The cycle must run the real ported verify core and derive its REAL
verdict -- so the signed scenario REDs against an impl that never emits, and the
unsigned/stale scenarios RED against an impl that always emits.

S1 (step-text uniqueness): every literal step string below is unique within the
feature directory. slice-03's steps speak of "whose gates pass" / "runs the
feature-end cycle" / "the cycle reports the feature-end is complete"; slice-04's
steps speak of "carries a human-signed coverage-map" / "carries an unsigned
coverage-map" / "signoff digest no longer matches its content" / "the two
coverage-map touchpoint records are now recorded" / "fully reconciled" / "from
its own check". No literal is shared across the slice step files (no shadow).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_04 import (
    CycleResult,
    FeatureEndCoverageMapComposition,
    IntegrityVerdict,
)
from .domain_types_slice_04 import CoverageMapDefect, CycleOutcome


scenarios("../slice-04-feature-end-coverage-map.feature")


@pytest.fixture
def composition(tmp_path: Path) -> FeatureEndCoverageMapComposition:
    return FeatureEndCoverageMapComposition(tmp_path)


@pytest.fixture
def result_holder() -> dict[str, object]:
    return {}


# --- Given --------------------------------------------------------------------


@given(
    "an orchestrator at the feature-end of a feature that carries a human-signed coverage-map"
)
def _given_signed_coverage_map(
    composition: FeatureEndCoverageMapComposition,
) -> None:
    # Stage a GENUINELY-signed coverage-map: the fixture computes the REAL §5.3
    # canonical digest over the body and records it. The cycle runs the real
    # ported verify core against it and reads a genuine PASS -- no injected
    # verdict.
    composition.stage_signed_coverage_map()


@given(
    parsers.parse(
        "an orchestrator at the feature-end of a feature whose coverage-map "
        "fails the verify core with a {defect} defect"
    ),
)
def _given_defective_coverage_map(
    composition: FeatureEndCoverageMapComposition,
    defect: str,
) -> None:
    # ONE parsed Given over the typed CoverageMapDefect enum stages every
    # refusal cause (Mandate-12 DSL template -- no per-defect literal decorator).
    # The Outline token is coerced to the enum SSOT (CoverageMapDefect(defect))
    # so the enum stays the single source of valid defects. The cycle's real
    # ported verify core derives the refusal from the staged artifact; the
    # verdict is the core's, never injected.
    composition.stage_coverage_map_with_defect(CoverageMapDefect(defect))


# --- When ---------------------------------------------------------------------


@when("the orchestrator runs the feature-end cycle through its coverage-map verify leg")
def _when_run_cycle(
    composition: FeatureEndCoverageMapComposition,
    result_holder: dict[str, object],
) -> None:
    result_holder["result"] = composition.run_cycle()


# --- Then ---------------------------------------------------------------------


@then("the cycle reports the feature-end is complete with the coverage-map verified")
def _then_cycle_complete(result_holder: dict[str, object]) -> None:
    result: CycleResult = result_holder["result"]  # type: ignore[assignment]
    assert result.outcome == CycleOutcome.SUCCEEDED


@then("the two coverage-map touchpoint records are now recorded")
def _then_coverage_map_records_present(
    composition: FeatureEndCoverageMapComposition,
    result_holder: dict[str, object],
) -> None:
    result: CycleResult = result_holder["result"]  # type: ignore[assignment]
    assert result.coverage_map_records >= composition.expected_coverage_map_records()


@then("the feature-end is reported as fully reconciled")
def _then_fully_reconciled(
    composition: FeatureEndCoverageMapComposition,
    result_holder: dict[str, object],
) -> None:
    integrity: IntegrityVerdict = composition.verify_integrity()
    assert integrity.exit_code == 0


@then("the cycle refuses to certify the feature-end is complete from its own check")
def _then_cycle_refuses_from_own_check(result_holder: dict[str, object]) -> None:
    result: CycleResult = result_holder["result"]  # type: ignore[assignment]
    # The refusal must come from the CYCLE's own fail-closed check (the ported
    # verify core refusing), NOT a dispatcher miss -- otherwise an unknown verb
    # would vacuously satisfy a refusal. `refused_by_cycle` requires the cycle's
    # structured `FeatureEndCycleRefused` marker, keeping this RED until the real
    # cycle runs the real ported verify and fail-closes for the right reason.
    assert result.outcome == CycleOutcome.REFUSED
    assert result.refused_by_cycle is True


@then("no coverage-map touchpoint record is recorded")
def _then_no_coverage_map_record(result_holder: dict[str, object]) -> None:
    result: CycleResult = result_holder["result"]  # type: ignore[assignment]
    # RM-1 anti-laundering: an unsigned / stale coverage-map mints NEITHER
    # record. A stub that always-emits would leave records here and fail.
    assert result.coverage_map_records == frozenset()
