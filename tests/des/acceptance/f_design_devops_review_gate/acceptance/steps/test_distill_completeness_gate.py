"""pytest-bdd binding for f-design-devops-review-gate slice-03 (DISTILL Phase-2.5).

Driving surface (Mandate-13 driving-port-only): the REAL spine
``wave_gate_stack_dispatch.resolve_stack`` over the SHIPPED nWave/waves/distill.yaml
registry (AT-10, Layer 3 composition) + the REAL production flavor parser
``flavor_dispatcher._parse_flavor_file`` over the SHIPPED nWave/flavors/atdd_pure.yaml
projecting ``lifecycle_events["dispatch.pre"]`` (AT-11, Layer 3 composition -- the
SAME artifact + parser the live carpaccio_intercept.evaluate_atdd_pure_dispatch
consumes). Step bodies delegate to the composition root
(composition_distill_completeness_gate.py); no business logic in step bodies
(Mandate-12).

Active-RED scaffold (atdd_pure -- NOT @skip): AT-10..11 are RED until DELIVER ships
(1) nWave/waves/distill.yaml carrying gate_stack.gate-out with the
check-slice-at-completeness row (the registry HOME, brief slice-06 reconciliation
-- NOT the flavor), and (2) the check-slice-at-completeness reference added to the
atdd_pure lifecycle_events["dispatch.pre"] carpaccio stack (the DELIVER-entry
backstop). The completeness CLI itself is ALREADY registered in the des dispatcher
(src/des/cli/__main__.py:74) -- slice-03 wires the two DATA-row REFERENCES, zero
new gate logic. Every RED fails with a semantic AssertionError naming the missing
seam, never a collection / import / setup error.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_distill_completeness_gate import DistillCompletenessGateComposition
from .domain_types_distill import DispatchLifecycle, WaveBoundary


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


@given(
    "the shipped atdd_pure flavor declares the DELIVER-entry dispatch.pre carpaccio stack"
)
def given_atdd_pure_flavor_declares_dispatch_pre(
    gate: DistillCompletenessGateComposition,
) -> None:
    gate.given_atdd_pure_flavor_declares_dispatch_pre()


# --- When ------------------------------------------------------------------


@when(
    "the dispatcher resolves the DISTILL gate-out stack from the registry as the default source"
)
def when_dispatcher_resolves_distill_gate_out_from_registry(
    gate: DistillCompletenessGateComposition,
) -> None:
    gate.when_dispatcher_resolves_distill_gate_out_from_registry(WaveBoundary.GATE_OUT)


@when("the dispatcher resolves the atdd_pure dispatch.pre stack as the default source")
def when_dispatcher_resolves_dispatch_pre_stack(
    gate: DistillCompletenessGateComposition,
) -> None:
    gate.when_dispatcher_resolves_dispatch_pre_stack(DispatchLifecycle.DISPATCH_PRE)


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


@then(
    "the resolved dispatch.pre gate-id sequence includes the check-slice-at-completeness gate"
)
def then_dispatch_pre_includes_check_slice_at_completeness(
    gate: DistillCompletenessGateComposition,
) -> None:
    gate.then_dispatch_pre_includes_check_slice_at_completeness(
        DispatchLifecycle.DISPATCH_PRE
    )


@then("the resolved dispatch.pre stack still includes the carpaccio-slice-gate gate")
def then_dispatch_pre_still_includes_carpaccio_gate(
    gate: DistillCompletenessGateComposition,
) -> None:
    gate.then_dispatch_pre_still_includes_carpaccio_gate(DispatchLifecycle.DISPATCH_PRE)
