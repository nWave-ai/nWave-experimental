"""pytest-bdd binding for slice-01 (the DISTILL gate-out registry-wiring slice).

Driving surface (Mandate-13 driving-port-only):
  * CT-1 / CT-2 -> Layer 3 composition: the REAL spine
    ``wave_gate_stack_dispatch.resolve_stack("distill","gate-out")`` reading the
    SHIPPED canonical registry ``nWave/waves/distill.yaml`` (the SOLE gate-stack
    source, ADR-FLOW-006 D6 -- NOT the dormant flavor block).
  * CT-3 -> Layer 3 composition: a read of the shipped ``nWave/flavors/atdd_pure.yaml``
    as DATA, witnessing the dormant ``wave_gate_stacks.distill`` co-tenant is GONE.
  * CT-4 / CT-5 -> Layer 3 composition: the REAL GOAL-CONTRACT scorecard module
    ``scripts/flow_v2_closure_scorecard.py`` (loaded by path -- ``from scripts.*``
    is forbidden per F-D-09), evaluating ``_module_wired`` for f-coherence's three
    modules (CT-4) and for a synthetic flavor-only gate id (CT-5, the tightening pin).

Step bodies delegate to ``DistillWiringComposition`` (Mandate-12: each body is a
single composition call; no control flow, no inline business logic).

active-RED scaffold (atdd_pure per-slice JIT -- NOT @skip): RED at HEAD for the
RIGHT reason (verified live this session):
  * CT-1: resolve_stack("distill","gate-out") == ["check-slice-at-completeness",
    "gate-design-at-coherence"] -- the two new gates ABSENT -> ordered-equality
    AssertionError (a NAMED semantic RED, never a collection/import error).
  * CT-2: the self-attest / verify-test-runner rows are ABSENT -> their on_failure
    is None != "warn" -> named RED.
  * CT-3: atdd_pure.yaml STILL carries wave_gate_stacks.distill -> named RED.
  * CT-4: the stale "gate-g" scorecard key is unregistered (False) + self-attest/
    test-runner only false-credit via the dormant flavor block -> not all three
    honestly live-resolve -> named RED.
  * CT-5: the scorecard has no _live_resolved tightening, so a synthetic flavor-only
    gate id evaluates _module_wired True -> named RED.

GREEN once DELIVER (1) appends the two registry rows to distill.yaml, (2) deletes
the dormant flavor block, (3) renames the scorecard gate-g key + adds the
_live_resolved live-resolution tightening (DDD-1/DDD-3/DDD-5/DDD-7).
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition import DistillWiringComposition


scenarios("../slice-01-distill-gate-out-resolves-four-gates-from-the-registry.feature")


# --- fixture (a fresh wiring composition per scenario) ----------------------


@pytest.fixture
def wiring() -> DistillWiringComposition:
    """A fresh DISTILL-wiring composition per scenario (the driving-port surface)."""
    return DistillWiringComposition()


# --- Given -- name the driving surface under witness ------------------------


@given("the DISTILL gate-out boundary")
def given_distill_gate_out_boundary(wiring: DistillWiringComposition) -> None:
    # No state to arm -- the boundary IS the registry-resolved surface the When drives.
    pass


@given("the closure scorecard goal contract")
def given_scorecard_goal_contract(wiring: DistillWiringComposition) -> None:
    # No state to arm -- the GOAL CONTRACT IS the scorecard module the When drives.
    pass


# --- When -- drive the REAL spine / read the flavor / drive the scorecard ----


@when("the gate-out stack is resolved from the live registry")
def when_stack_resolved(wiring: DistillWiringComposition) -> None:
    wiring.when_the_distill_gate_out_stack_is_resolved()


@when("the flavor file is inspected for the dormant DISTILL co-tenant")
def when_flavor_inspected(wiring: DistillWiringComposition) -> None:
    wiring.when_the_flavor_file_is_inspected_for_the_dormant_block()


@when("the scorecard evaluates the coherence feature's wired modules")
def when_scorecard_evaluates_modules(wiring: DistillWiringComposition) -> None:
    wiring.when_the_scorecard_evaluates_coherence_wired_modules()


@when("the scorecard evaluates a gate present only as a flavor string")
def when_scorecard_evaluates_synthetic(wiring: DistillWiringComposition) -> None:
    wiring.when_the_scorecard_evaluates_a_dormant_flavor_only_gate()


# --- Then -- observable readers ---------------------------------------------


@then("the boundary resolves the four gates in declared order")
def then_four_gates_in_order(wiring: DistillWiringComposition) -> None:
    wiring.then_the_four_gates_resolve_in_declared_order()


@then("both newly wired gates surface their objection without vetoing the return")
def then_new_rows_warn(wiring: DistillWiringComposition) -> None:
    wiring.then_both_new_rows_are_warn()


@then("the dormant flavor co-tenant is absent")
def then_dormant_block_absent(wiring: DistillWiringComposition) -> None:
    wiring.then_the_dormant_flavor_block_is_absent()


@then("every coherence wired module is counted wired from live resolution")
def then_all_modules_live_resolve(wiring: DistillWiringComposition) -> None:
    wiring.then_all_coherence_modules_live_resolve()


@then("the flavor-only gate is not counted wired")
def then_synthetic_not_wired(wiring: DistillWiringComposition) -> None:
    wiring.then_the_dormant_flavor_only_gate_is_not_wired()
