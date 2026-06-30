"""pytest-bdd binding for f-design-devops-review-gate slice-01 (walking skeleton).

Driving surface (Mandate-13 driving-port-only): the REAL spine
``wave_gate_stack_dispatch.resolve_stack`` over the SHIPPED nWave/waves/design.yaml
registry (AT-1, Layer 3 composition) + the REAL ``des record-design-review`` /
``des verify-design-review`` CLIs as subprocesses (AT-2..4, Layer 3 subprocess).
Step bodies delegate to the composition root (composition_design_review_gate.py);
no business logic in step bodies (Mandate-12).

Active-RED scaffold (atdd_pure -- NOT @skip): each scenario is RED until DELIVER
ships (1) nWave/waves/design.yaml carrying gate_stack.gate-out with the
verify-design-review row + (2) the verify-design-review / record-design-review CLIs
registered in the des dispatcher. Every case fails with a semantic AssertionError
naming the missing registry / CLI seam, never a collection / import / setup error.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_design_review_gate import DesignReviewGateComposition
from .domain_types import ReviewerVerdict, WaveBoundary


scenarios("../design-review-gate.feature")


@pytest.fixture
def gate(tmp_path) -> DesignReviewGateComposition:
    return DesignReviewGateComposition(repo_dir=tmp_path)


# --- Given -----------------------------------------------------------------


@given(
    "the canonical wave-contract registry file for the DESIGN wave is shipped in the repo"
)
def given_design_registry_file_is_shipped(
    gate: DesignReviewGateComposition,
) -> None:
    gate.given_design_registry_file_is_shipped()


@given("a DESIGN feature with a feature-delta and no recorded review verdict")
def given_design_feature_with_no_recorded_verdict(
    gate: DesignReviewGateComposition,
) -> None:
    gate.given_design_feature_with_no_recorded_verdict()


# --- When ------------------------------------------------------------------


@when(
    "the dispatcher resolves the DESIGN gate-out stack from the registry as the default source"
)
def when_dispatcher_resolves_design_gate_out_from_registry(
    gate: DesignReviewGateComposition,
) -> None:
    gate.when_dispatcher_resolves_design_gate_out_from_registry(WaveBoundary.GATE_OUT)


@when(
    "the solution-architect-reviewer records an approved review verdict for that feature"
)
def when_reviewer_records_approved(gate: DesignReviewGateComposition) -> None:
    gate.when_reviewer_records_verdict(ReviewerVerdict.APPROVED)


@when(
    "the solution-architect-reviewer records a needs-revision review verdict for that feature"
)
def when_reviewer_records_needs_revision(
    gate: DesignReviewGateComposition,
) -> None:
    gate.when_reviewer_records_verdict(ReviewerVerdict.NEEDS_REVISION)


@when("the DESIGN review-verdict gate is verified for that feature")
def when_design_review_gate_is_verified(
    gate: DesignReviewGateComposition,
) -> None:
    gate.when_design_review_gate_is_verified()


# --- Then ------------------------------------------------------------------


@then(
    "the resolved gate-id sequence equals the DESIGN gate-out sequence the registry file declares"
)
def then_resolved_sequence_equals_registry_declared(
    gate: DesignReviewGateComposition,
) -> None:
    gate.then_resolved_sequence_equals_registry_declared(WaveBoundary.GATE_OUT)


@then("the resolved DESIGN gate-out stack includes the verify-design-review gate")
def then_resolved_stack_includes_verify_design_review(
    gate: DesignReviewGateComposition,
) -> None:
    gate.then_resolved_stack_includes_verify_design_review(WaveBoundary.GATE_OUT)


@then("the gate refuses the DESIGN return with verdict indeterminate")
def then_gate_refuses_with_indeterminate(
    gate: DesignReviewGateComposition,
) -> None:
    gate.then_gate_refuses_with_indeterminate()


@then("the gate passes the DESIGN return with verdict pass")
def then_gate_passes_with_pass(gate: DesignReviewGateComposition) -> None:
    gate.then_gate_passes_with_pass()


@then("the gate vetoes the DESIGN return with verdict vetoed")
def then_gate_vetoes_with_vetoed(gate: DesignReviewGateComposition) -> None:
    gate.then_gate_vetoes_with_vetoed()
