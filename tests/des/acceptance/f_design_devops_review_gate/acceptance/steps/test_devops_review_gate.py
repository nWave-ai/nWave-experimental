"""pytest-bdd binding for f-design-devops-review-gate slice-02 (DEVOPS + lift).

Driving surface (Mandate-13 driving-port-only): the REAL spine
``wave_gate_stack_dispatch.resolve_stack`` over the SHIPPED nWave/waves/devops.yaml
registry (AT-5, Layer 3 composition) + the REAL ``des record-devops-review`` /
``des verify-devops-review`` CLIs as subprocesses (AT-6..8, Layer 3 subprocess) +
the REAL ``SubagentStopService.validate`` production composition root (AT-9, the
literal-lift seam, Layer 3 composition). Step bodies delegate to the composition
root (composition_devops_review_gate.py); no business logic in step bodies
(Mandate-12).

Active-RED scaffold (atdd_pure -- NOT @skip): AT-5..9 are RED until DELIVER ships
(1) nWave/waves/devops.yaml carrying gate_stack.gate-out with the
verify-devops-review row, (2) the verify-devops-review / record-devops-review CLIs
registered in the des dispatcher, and (3) the "discuss" literal in
subagent_stop_service.py:307/311/317 lifted to the active wave. The DISCUSS-
regression safety of that same lift is covered by the shipped DISCUSS gate-out ATs
(tests/des/acceptance/oss_review_verdict_demotion/ + nwave_flow_v2_enforcement/),
not a separate pin here (carpaccio-ceiling de-dup). Every RED fails with a semantic
AssertionError naming the missing seam, never a collection / import / setup error.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_devops_review_gate import DevopsReviewGateComposition
from .domain_types_devops import ReviewerVerdict, WaveBoundary, WaveFloor


scenarios("../devops-review-gate.feature")


@pytest.fixture
def gate(tmp_path) -> DevopsReviewGateComposition:
    return DevopsReviewGateComposition(repo_dir=tmp_path)


# --- Given -----------------------------------------------------------------


@given(
    "the canonical wave-contract registry file for the DEVOPS wave is shipped in the repo"
)
def given_devops_registry_file_is_shipped(
    gate: DevopsReviewGateComposition,
) -> None:
    gate.given_devops_registry_file_is_shipped()


@given("a DEVOPS feature with a feature-delta and no recorded review verdict")
def given_devops_feature_with_no_recorded_verdict(
    gate: DevopsReviewGateComposition,
) -> None:
    gate.given_devops_feature_with_no_recorded_verdict()


@given("a DEVOPS wave-active floor and a feature-delta with no recorded review verdict")
def given_devops_floor_and_feature_delta_no_verdict(
    gate: DevopsReviewGateComposition,
) -> None:
    gate.given_devops_floor_and_feature_delta_no_verdict()


# --- When ------------------------------------------------------------------


@when(
    "the dispatcher resolves the DEVOPS gate-out stack from the registry as the default source"
)
def when_dispatcher_resolves_devops_gate_out_from_registry(
    gate: DevopsReviewGateComposition,
) -> None:
    gate.when_dispatcher_resolves_devops_gate_out_from_registry(WaveBoundary.GATE_OUT)


@when(
    "the platform-architect-reviewer records an approved review verdict for that feature"
)
def when_reviewer_records_approved(gate: DevopsReviewGateComposition) -> None:
    gate.when_reviewer_records_verdict(ReviewerVerdict.APPROVED)


@when(
    "the platform-architect-reviewer records a needs-revision review verdict for that feature"
)
def when_reviewer_records_needs_revision(
    gate: DevopsReviewGateComposition,
) -> None:
    gate.when_reviewer_records_verdict(ReviewerVerdict.NEEDS_REVISION)


@when("the DEVOPS review-verdict gate is verified for that feature")
def when_devops_review_gate_is_verified(
    gate: DevopsReviewGateComposition,
) -> None:
    gate.when_devops_review_gate_is_verified()


@when(
    "the platform-architect returns the DEVOPS output through the live SubagentStop gate"
)
def when_platform_architect_returns_devops_output(
    gate: DevopsReviewGateComposition,
) -> None:
    gate.when_output_returned_through_live_subagent_stop_gate(WaveFloor.DEVOPS)


# --- Then ------------------------------------------------------------------


@then(
    "the resolved gate-id sequence equals the DEVOPS gate-out sequence the registry file declares"
)
def then_resolved_sequence_equals_registry_declared(
    gate: DevopsReviewGateComposition,
) -> None:
    gate.then_resolved_sequence_equals_registry_declared(WaveBoundary.GATE_OUT)


@then("the resolved DEVOPS gate-out stack includes the verify-devops-review gate")
def then_resolved_stack_includes_verify_devops_review(
    gate: DevopsReviewGateComposition,
) -> None:
    gate.then_resolved_stack_includes_verify_devops_review(WaveBoundary.GATE_OUT)


@then("the gate refuses the DEVOPS return with verdict indeterminate")
def then_gate_refuses_with_indeterminate(
    gate: DevopsReviewGateComposition,
) -> None:
    gate.then_gate_refuses_with_indeterminate()


@then("the gate passes the DEVOPS return with verdict pass")
def then_gate_passes_with_pass(gate: DevopsReviewGateComposition) -> None:
    gate.then_gate_passes_with_pass()


@then("the gate vetoes the DEVOPS return with verdict vetoed")
def then_gate_vetoes_with_vetoed(gate: DevopsReviewGateComposition) -> None:
    gate.then_gate_vetoes_with_vetoed()


@then("the live gate blocks the DEVOPS return naming the absent devops review verdict")
def then_live_gate_blocks_naming_absent_devops_verdict(
    gate: DevopsReviewGateComposition,
) -> None:
    gate.then_live_gate_blocks_naming_absent_devops_verdict()
