"""Slice-03 acceptance: the nw-deliver skill prose agrees with the runtime.

Layer 3 subprocess + artifact-read (Mandate-9 example-only at layer 3).
Driving observables: the shipped ``python -m des.cli.phases`` CLI (subprocess)
and the real ``nw-deliver/SKILL.md`` prose artifact. Mandate-13: no direct
``des.domain`` / ``des.application`` / ``des.adapters`` import — the runtime
phase set is obtained only through the CLI driving port.

The expected phase set is DERIVED from the live runtime CLI, never hand-restated,
so the parity check cannot drift from the code.
"""

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then

from .steps.composition import ParityComposition
from .steps.domain_types import DeliverySkill


_HERE = Path(__file__).resolve().parent
scenarios(str(_HERE / "steps" / "atdd_pure_prose_runtime_parity.feature"))


@pytest.fixture
def composition() -> ParityComposition:
    return ParityComposition()


@pytest.fixture
def parity() -> dict:
    return {}


@given("the running system's canonical delivery phases")
def _runtime_phases(composition: ParityComposition, parity: dict) -> None:
    parity["runtime"] = composition.runtime_phase_model()


@given("the delivery skill the operator reads")
def _documented_phases(composition: ParityComposition, parity: dict) -> None:
    parity["documented"] = composition.documented_phase_model(DeliverySkill.NW_DELIVER)


@then("the delivery skill names every phase the running system executes")
def _names_every_runtime_phase(composition: ParityComposition, parity: dict) -> None:
    assert (
        composition.canonical_names_absent_from_prose(
            parity["documented"], parity["runtime"]
        )
        == frozenset()
    )


@then("the delivery skill mentions no delivery phase the running system retired")
def _mentions_no_retired_phase(composition: ParityComposition, parity: dict) -> None:
    assert (
        composition.retired_phase_tokens_in_prose(
            parity["documented"], parity["runtime"]
        )
        == frozenset()
    )


@then("the delivery skill makes no stale claim about the number of phases")
def _no_stale_count_claim(composition: ParityComposition, parity: dict) -> None:
    assert (
        composition.stale_count_phrases_in_prose(
            parity["documented"], parity["runtime"]
        )
        == frozenset()
    )
