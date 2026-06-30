"""pytest-bdd binding for slice-04 (the coherence-gate WIRING slice).

Driving surface (Mandate-13 driving-port-only):
  * REGISTRY (CT-8) -> Layer 3 subprocess: the REAL ``des`` dispatcher recognizing
    ``des gate-design-at-coherence`` (vs argparse's unknown-subcommand rejection).
  * CATALOG (CT-8) -> the shipped ``nWave/gates/_catalog.yaml`` mirror entry (DATA
    the SUT ships; the CI arch test enforces registry<->catalog 1:1 parity).
  * GATE_STACK (CT-9 / AT-A1) -> Layer 3 composition: the REAL spine
    ``wave_gate_stack_dispatch.resolve_stack("distill","gate-out")`` -- the SOLE
    gate-stack source (ADR-FLOW-006 D6), the registry HOME, NOT the dormant flavor
    block (ground-truth reconciliation; see composition_wiring.py).
  * don't-break-spine (CT-9 / §22.0) -> Layer 3 subprocess: the REAL
    ``des gate-design-at-coherence`` over a neither-contract feature-root -> the §17
    verdict must be NOT_APPLICABLE (a NA never vetoes the DISTILL return).

Step bodies delegate to ``WiringComposition`` (Mandate-12: each body <=2 statements
ending in a composition call; no control flow). The verdict ``Then`` for the
neither-contract leg is slice-04-unique (it names a non-blocking NA rather than the
slice-01/03 verdict matcher), so it is declared here, not imported from
``common_steps``.

active-RED scaffold (atdd_pure per-slice JIT -- NOT @skip): RED at HEAD for the
RIGHT reason. Verified live:
  * CT-8 REGISTRY: ``gate-design-at-coherence`` is an INVALID dispatcher choice at
    HEAD (the live subcommand is ``gate-g``; slice-04 RENAMES it) -> the recognition
    reader returns False -> a NAMED semantic AssertionError (the SubcommandRow is
    absent), never an import/collection error.
  * CT-8 CATALOG: the catalog has a ``gate-g`` entry, not ``gate-design-at-coherence``
    -> the membership reader returns False -> named RED.
  * CT-9 GATE_STACK: ``resolve_stack("distill","gate-out") ==
    ["check-slice-at-completeness"]`` at HEAD -- gate-G ABSENT -> named RED.
  * don't-break-spine: the subcommand is UNRECOGNIZED at HEAD -> no verdict emitted
    -> the NA Then fires the named RED (the subcommand was rejected). GREEN once
    DELIVER wires + renames the subcommand and the neither-contract path returns NA.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_wiring import WiringComposition
from .domain_types import WiringSurface


scenarios(
    "../slice-04-coherence-gate-is-wired-and-fires-without-breaking-the-spine.feature"
)


# --- fixture (a fresh wiring composition per scenario) ----------------------


@pytest.fixture
def wiring() -> WiringComposition:
    """A fresh wiring composition per scenario (the shared driving-port surface)."""
    return WiringComposition()


# --- CT-8: registry + catalog -----------------------------------------------


@given("the coherence gate is wired into the operator subcommand registry surface")
def given_registry_surface(wiring: WiringComposition) -> None:
    wiring.given_wiring_surface(WiringSurface.REGISTRY)


@given("the coherence gate is wired into the live DISTILL gate-out stack surface")
def given_gate_stack_surface(wiring: WiringComposition) -> None:
    wiring.given_wiring_surface(WiringSurface.GATE_STACK)


@when("the wiring surface is inspected")
def when_surface_inspected(wiring: WiringComposition) -> None:
    wiring.when_the_wiring_surface_is_inspected()


@then("the operator dispatcher recognizes the coherence gate subcommand")
def then_subcommand_recognized(wiring: WiringComposition) -> None:
    wiring.then_the_subcommand_is_recognized()


@then("the coherence gate appears in the gate catalog surface")
def then_catalog_has_gate(wiring: WiringComposition) -> None:
    wiring.then_catalog_mirror_carries_gate()


@then("the coherence gate is live-resolved in the DISTILL gate-out stack")
def then_live_resolved(wiring: WiringComposition) -> None:
    wiring.then_gate_is_live_resolved_in_distill_gate_out()


# --- don't-break-spine: neither-contract -> NOT_APPLICABLE, non-blocking ----


@given("a feature whose DISTILL return ships no design contract")
def given_no_contract_feature(wiring: WiringComposition) -> None:
    wiring.given_a_feature_with_no_design_contract()


@when("the wired coherence gate fires on the feature that ships no design contract")
def when_gate_fires_no_contract(wiring: WiringComposition, tmp_path: Path) -> None:
    wiring.when_the_subcommand_fires_on_a_feature_with_no_design_contract(tmp_path)


@then(
    "the coherence gate returns a not-applicable verdict that does not block the return"
)
def then_na_non_blocking(wiring: WiringComposition) -> None:
    wiring.then_the_verdict_is_not_applicable_and_does_not_block()
