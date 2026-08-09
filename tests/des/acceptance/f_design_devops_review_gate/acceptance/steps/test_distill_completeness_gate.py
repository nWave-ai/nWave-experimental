"""pytest-bdd binding for f-design-devops-review-gate slice-03 (DISTILL Phase-2.5).

Driving surface (Mandate-13 driving-port-only): the REAL spine
``wave_gate_stack_dispatch.resolve_stack`` over the SHIPPED nWave/waves/distill.yaml
registry (AT-10, Layer 3 composition). Step bodies delegate to the composition root
(composition_distill_completeness_gate.py); no business logic in step bodies
(Mandate-12).

Active-RED scaffold (atdd_pure -- NOT @skip): AT-10 is RED until DELIVER ships
nWave/waves/distill.yaml carrying gate_stack.gate-out with the
check-slice-at-completeness row (the registry HOME, brief slice-06 reconciliation
-- NOT the flavor). The completeness CLI itself is ALREADY registered in the des dispatcher
(src/des/cli/__main__.py:74) -- slice-03 wires the DATA-row REFERENCE, zero
new gate logic. Every RED fails with a semantic AssertionError naming the missing
seam, never a collection / import / setup error.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_distill_completeness_gate import DistillCompletenessGateComposition
from .domain_types_distill import WaveBoundary


scenarios("../distill-completeness-gate.feature")


@pytest.fixture
def gate(tmp_path) -> DistillCompletenessGateComposition:
    return DistillCompletenessGateComposition(repo_dir=tmp_path)


# --- Given -----------------------------------------------------------------


@given(
    "the canonical wave-contract registry file for the DISTILL wave is shipped in the repo"
)
def given_distill_registry_file_is_shipped(
    gate: DistillCompletenessGateComposition,
) -> None:
    gate.given_distill_registry_file_is_shipped()


# --- When ------------------------------------------------------------------


@when(
    "the dispatcher resolves the DISTILL gate-out stack from the registry as the default source"
)
def when_dispatcher_resolves_distill_gate_out_from_registry(
    gate: DistillCompletenessGateComposition,
) -> None:
    gate.when_dispatcher_resolves_distill_gate_out_from_registry(WaveBoundary.GATE_OUT)


# --- Then ------------------------------------------------------------------


@then(
    "the resolved gate-id sequence equals the DISTILL gate-out sequence the registry file declares"
)
def then_resolved_sequence_equals_registry_declared(
    gate: DistillCompletenessGateComposition,
) -> None:
    gate.then_resolved_sequence_equals_registry_declared(WaveBoundary.GATE_OUT)


@then(
    "the resolved DISTILL gate-out stack includes the check-slice-at-completeness gate"
)
def then_resolved_stack_includes_check_slice_at_completeness(
    gate: DistillCompletenessGateComposition,
) -> None:
    gate.then_resolved_stack_includes_check_slice_at_completeness(WaveBoundary.GATE_OUT)
