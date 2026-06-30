"""pytest-bdd binding for f-declarative-gate-composition slice-01 (walking skeleton).

Driving surface (Mandate-13 driving-port-only): the REAL spine services via the
production composition root (Layer 3 composition), the REAL resolve_wave_gate_stack
pure seam over the shipped flavor file, and the REAL des verify-discuss-review
subcommand (Layer 3 subprocess). Step bodies delegate to the composition root
(composition_slice_01_walking_skeleton.py); no business logic in step bodies
(Mandate-12). The <boundary>/<site> parameters parse once into typed enums, so one
scenario shape ranges over the DISCUSS gate-in/gate-out boundaries.

Active-RED scaffold (atdd_pure -- NOT @skip): each scenario is RED until DELIVER
ships the four net-new seams (resolve_wave_gate_stack, the wave_gate_stacks.discuss
block, GateInvocationResult.recovery_suggestions, the verify-discuss-review catalog
gate). Every case fails with a semantic AssertionError naming the missing seam,
never a collection / import / setup error.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_01_walking_skeleton import DeclarativeGateStackComposition
from .domain_types_declarative_gate_composition import DiscussVetoSite, WaveBoundary


scenarios("../slice-01-walking-skeleton.feature")


@pytest.fixture
def stack() -> DeclarativeGateStackComposition:
    return DeclarativeGateStackComposition()


# --- Given -----------------------------------------------------------------


@given(
    parsers.parse(
        "the DISCUSS gate stack is declared and the {site} precondition is armed"
    )
)
def given_discuss_gate_stack_declared(
    stack: DeclarativeGateStackComposition, site: str, tmp_path: Path
) -> None:
    stack.given_discuss_gate_stack_declared(tmp_path, DiscussVetoSite[site])


# --- When ------------------------------------------------------------------


@when(
    parsers.parse(
        "the active discuss-wave dispatch iterates the declared {boundary} stack"
    )
)
def when_active_wave_dispatch_iterates_declared_stack(
    stack: DeclarativeGateStackComposition, boundary: str
) -> None:
    stack.when_active_wave_dispatch_iterates_declared_stack()


# --- Then ------------------------------------------------------------------


@then(parsers.parse("the declared discuss {boundary} stack is the source of the veto"))
def then_declared_stack_is_the_veto_source(
    stack: DeclarativeGateStackComposition, boundary: str
) -> None:
    stack.then_declared_stack_is_the_veto_source(WaveBoundary(boundary))


@then(parsers.parse("the {boundary} veto still blocks the dispatch"))
def then_the_boundary_veto_still_blocks(
    stack: DeclarativeGateStackComposition, boundary: str
) -> None:
    stack.then_the_boundary_veto_still_blocks()


@then(parsers.parse("the block names the {boundary} reason"))
def then_block_names_the_boundary_reason(
    stack: DeclarativeGateStackComposition, boundary: str
) -> None:
    stack.then_block_names_the_boundary_reason()


@then("the block carries the recovery with parity to the imperative branch")
def then_recovery_is_carried_with_parity(
    stack: DeclarativeGateStackComposition,
) -> None:
    stack.then_recovery_is_carried_with_parity()


@then("the PO-review consumer veto is a registered catalog gate")
def then_po_review_veto_gate_is_catalogued(
    stack: DeclarativeGateStackComposition,
) -> None:
    stack.then_po_review_veto_gate_is_catalogued()


@then("the wave gate-in stack composes before the wave-agnostic dispatch")
def then_gate_in_composes_before_wave_agnostic_dispatch(
    stack: DeclarativeGateStackComposition,
) -> None:
    stack.then_gate_in_composes_before_wave_agnostic_dispatch()
