"""Step definitions for slice-03 -- the `des feature-end run` feature-end-cycle CLI.

slice-03 of oss-feature-end-emit-cli (DDD-7 RATIFIED 2026-06-03; ATs REVISED
2026-06-03 to close the verdict-laundering gap the C_REVIEWER_AUDIT caught).

Step bodies are delegate-only (Mandate-12 criterion 3): each is a single
`FeatureEndCycleComposition` call + one observable assertion. All orchestration
logic lives in the production `des feature-end run` subcommand (a thin shim over
the platform-agnostic feature-end-cycle use-case that RUNS the 2 already-CLI'd
gates, then signs (slice-02) + emits (slice-01)); the composition root only
wires the real subprocess, stages the gate ENVIRONMENT (a real installable
feature workspace -- never an injected verdict), reads the gate-heartbeat +
feature-end records back through the production `AtCompletionLedger` reader (the
audit substrate `des verify-integrity` consumes), and feeds the post-cycle
ledger to the real `des verify-integrity` consumer to pin partial-done honesty.

VERDICT-LAUNDERING CLOSE-OUT: the Given steps stage the gate ENVIRONMENT (a
passing installable feature, or a broken feature whose REAL walking-skeleton
gate fails on its build leg), NOT a `--walking-skeleton-outcome` verdict. The
cycle must run the real gates and derive their REAL verdicts -- so these ATs RED
against the laundering A_GREEN code that minted heartbeats from the (now-dropped)
input flag.

S1 (step-text uniqueness): every literal step string below is unique within the
feature directory. slice-01's steps speak of "records ... to the completion
ledger"; slice-02's steps speak of "signs a deep-review verdict ... into a
verdict hash"; slice-03's steps speak of "runs the feature-end cycle" + "left a
heartbeat showing it ran" + "still missing" + "reachable through the single
entry point ... cycle verb". No literal is shared across the slice step files
(no shadow).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_03 import FeatureEndCycleComposition, FeatureEndCycleResult
from .domain_types_slice_03 import CycleOutcome, FeatureEndRecord


scenarios("../slice-03-feature-end-run.feature")


@pytest.fixture
def composition(tmp_path: Path) -> FeatureEndCycleComposition:
    return FeatureEndCycleComposition(tmp_path)


@pytest.fixture
def result_holder() -> dict[str, object]:
    return {}


# --- Given --------------------------------------------------------------------


@given("an orchestrator at the feature-end of a feature whose gates pass")
def _given_gates_pass(composition: FeatureEndCycleComposition) -> None:
    # Stage the gate ENVIRONMENT (a real installable feature whose REAL gate
    # runs reach PASS), NOT the verdict. The cycle runs the real gates against
    # this workspace and reads their genuine PASS verdicts -- no injected outcome.
    composition.stage_passing_feature()


@given(
    "an orchestrator at the feature-end of a feature whose gates pass and whose "
    "coverage-map is human-signed"
)
def _given_gates_pass_signed_coverage_map(
    composition: FeatureEndCycleComposition,
) -> None:
    # slice-04 made the coverage-map verify leg a HARD precondition of cycle
    # success. Stage the passing gate environment PLUS a GENUINELY-signed
    # coverage-map (real §5.3 digest, via the SHARED builder slice-04 uses) so
    # the now-mandatory leg PASSES and the cycle reaches a full 6-record SUCCESS.
    # The verdict is the real ported verify core's, derived from the staged
    # artifact -- never injected.
    composition.stage_passing_signed_feature()


@given(
    "an orchestrator at the feature-end of a feature whose gates pass but whose "
    "coverage-map is not signed"
)
def _given_gates_pass_unsigned_coverage_map(
    composition: FeatureEndCycleComposition,
) -> None:
    # Stage the passing gate environment PLUS a genuinely-UNSIGNED coverage-map
    # (the producer's `_pending_` digest; no human signed). The cycle's REAL
    # coverage-map verify leg refuses and mints NEITHER coverage-map record, so
    # `des verify-integrity` honestly reports them still missing.
    composition.stage_passing_unsigned_feature()


@given(
    "an orchestrator at the feature-end of a feature whose walking-skeleton gate fails"
)
def _given_walking_skeleton_fails(composition: FeatureEndCycleComposition) -> None:
    # Stage a real broken feature (no pyproject.toml) so the REAL
    # walking-skeleton gate's build leg genuinely FAILS (ArtifactBuildError ->
    # at_failure, exit 1) BEFORE any wheel/network. The cycle must read this
    # REAL fail verdict and fail-close -- the verdict is the gate's, not the test's.
    composition.stage_walking_skeleton_failing_feature()


# --- When ---------------------------------------------------------------------


@when("the orchestrator runs the feature-end cycle")
def _when_run_cycle(
    composition: FeatureEndCycleComposition,
    result_holder: dict[str, object],
) -> None:
    result_holder["result"] = composition.run_cycle()


@when("the consolidated feature-end command surface is probed for its verbs")
def _when_probe_verbs(
    composition: FeatureEndCycleComposition,
    result_holder: dict[str, object],
) -> None:
    result_holder["advertises_run"] = composition.feature_end_namespace_advertises_run()


# --- Then ---------------------------------------------------------------------


@then("the cycle reports the feature-end is complete")
def _then_cycle_complete(result_holder: dict[str, object]) -> None:
    result: FeatureEndCycleResult = result_holder["result"]  # type: ignore[assignment]
    assert result.outcome == CycleOutcome.SUCCEEDED


@then("the ledger carries a heartbeat for every gate the cycle ran")
def _then_all_gate_heartbeats(
    composition: FeatureEndCycleComposition,
    result_holder: dict[str, object],
) -> None:
    result: FeatureEndCycleResult = result_holder["result"]  # type: ignore[assignment]
    assert result.gate_records >= composition.expected_gate_records()


@then("the ledger carries the batch-refactor and signed deep-review records")
def _then_feature_end_records(
    composition: FeatureEndCycleComposition,
    result_holder: dict[str, object],
) -> None:
    result: FeatureEndCycleResult = result_holder["result"]  # type: ignore[assignment]
    assert result.feature_end_records >= composition.expected_feature_end_records()


@then("the ledger carries both coverage-map touchpoint records from a genuine signoff")
def _then_coverage_map_records_present(
    composition: FeatureEndCycleComposition,
) -> None:
    # The 6th-record proof: the cycle's REAL coverage-map verify leg PASSED on
    # the genuinely-signed map and appended both CoverageMapVerifiedAt* records
    # (RM-1: present <=> a real signed verify passed). Read back through the SAME
    # production ledger reader slice-04 uses.
    assert (
        composition.ledger_coverage_map_records()
        >= composition.expected_coverage_map_records()
    )


@then("the walking-skeleton gate left a heartbeat showing it ran")
def _then_walking_skeleton_ran(composition: FeatureEndCycleComposition) -> None:
    assert composition.walking_skeleton_gate_ran() is True


@then("the environmental-e2e gate left a heartbeat showing it ran")
def _then_environmental_e2e_ran(composition: FeatureEndCycleComposition) -> None:
    assert composition.environmental_e2e_gate_ran() is True


@then("the cycle refuses to certify the feature-end is complete")
def _then_cycle_refuses(result_holder: dict[str, object]) -> None:
    result: FeatureEndCycleResult = result_holder["result"]  # type: ignore[assignment]
    # The refusal must come from the CYCLE's own fail-closed check, NOT a
    # dispatcher miss -- otherwise an unknown `des feature-end run` verb would
    # vacuously satisfy a refusal. `refused_by_cycle` requires the cycle's
    # structured `FeatureEndCycleRefused` marker, keeping this RED until the real
    # cycle exists and fail-closes for the right reason (the same vacuous-refusal
    # trap slice-02's `refused_by_signer` closes).
    assert result.outcome == CycleOutcome.REFUSED
    assert result.refused_by_cycle is True


@then("the ledger carries no signed deep-review record")
def _then_no_signed_deep_review(result_holder: dict[str, object]) -> None:
    result: FeatureEndCycleResult = result_holder["result"]  # type: ignore[assignment]
    assert FeatureEndRecord.DEEP_REVIEW_VERDICT.value not in result.feature_end_records


@then(
    "the integrity report stays honest that the feature-end is not yet fully reconciled"
)
def _then_not_fully_reconciled(
    composition: FeatureEndCycleComposition,
    result_holder: dict[str, object],
) -> None:
    # Under slice-04's moved boundary the unsigned coverage-map makes the cycle
    # refuse and mint NEITHER coverage-map record, so `des verify-integrity`
    # honestly reports the feature NOT fully reconciled (non-zero exit). This is
    # the scenario-4 honesty value -- distinct from slice-04 AT-2 (which asserts
    # the cycle's OWN FeatureEndCycleRefused marker); here we assert the
    # downstream integrity SUBSTRATE stays honest.
    result_holder["integrity"] = composition.verify_integrity()
    assert result_holder["integrity"].exit_code != 0  # type: ignore[union-attr]


@then("the integrity report names the coverage-map touchpoint records as still missing")
def _then_coverage_map_missing(
    composition: FeatureEndCycleComposition,
    result_holder: dict[str, object],
) -> None:
    integrity = result_holder["integrity"]
    assert integrity.missing_records >= composition.coverage_map_records_still_missing()  # type: ignore[union-attr]


@then("the feature-end cycle verb is reachable through the single entry point")
def _then_run_verb_reachable(result_holder: dict[str, object]) -> None:
    assert result_holder["advertises_run"] is True


@then("the feature-end signing verb is still reachable through the single entry point")
def _then_sign_verb_still_reachable(
    composition: FeatureEndCycleComposition,
    result_holder: dict[str, object],
) -> None:
    # The same `des feature-end --help` probe that advertises `run` also
    # advertises `sign` (DDD-7 single-entry-point: the new verb consolidates
    # alongside slice-02's, no top-level proliferation). `feature_end_namespace_
    # advertises_run` requires BOTH verbs, so a True here is the back-compat proof.
    assert result_holder["advertises_run"] is True
