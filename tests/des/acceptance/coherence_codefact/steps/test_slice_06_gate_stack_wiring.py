"""pytest-bdd binding for the f-coherence-and-attestation slice-06 scenarios (gate-stack wiring).

Driving surface (Mandate-13 driving-port-only): the REAL ``des`` dispatcher
subprocess (registration + behavioural drive) + the REAL shipped
``nWave/flavors/*.yaml`` artifacts (the gate-stack reference closure). Step bodies
delegate to the composition root (``composition_slice_06_gate_stack_wiring.py``);
no business logic in step bodies (Mandate-12 — ≤2 statements, final statement is a
composition method call, no control flow). The ``<subcommand>`` parameter is parsed
once into the typed ``WiredModuleSpec``, so ONE scenario shape ranges over the three
modules (DSL emergence over the ``WiredModule`` enum, not decorator proliferation).

active-RED scaffold (atdd_pure — NOT @skip): every scenario is RED until DELIVER
wires the slice-06 seams — the three ``_REGISTRY`` rows + catalog mirrors, the
flavor gate-stack references, and the thin gate-g / self-attest CLI wrappers. Each
scenario fails with a semantic AssertionError naming the missing wiring, never a
collection / import / setup error (the dispatcher imports cleanly; only the
_REGISTRY rows are absent).

STEP-TEXT UNIQUENESS (S1): every literal/template step phrase below is DISTINCT
from the slice-01..05 step phrases. slice-01 "is asked for the fact through the
CodeFactPort"; slice-02 "answers the structural fact" / "negotiates the best
available provider"; slice-03 "diffs the design contract against the acceptance
tests"; slice-05 "resolving the runner" / "the slice gate runs". slice-06 uses
"the registration of the subcommand is inspected through the real des dispatcher"
/ "the gate-stack reference of the module is inspected" / "the subcommand is driven
end to end through the real des dispatcher" — no pytest-bdd global-registry shadow.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_06_gate_stack_wiring import GateStackWiringComposition
from .domain_types_slice_06_gate_stack_wiring import (
    SPEC_BY_SUBCOMMAND,
    UNKNOWN_SUBCOMMAND_SPEC,
)


scenarios("../slice-06-gate-stack-wiring.feature")


@pytest.fixture
def wiring() -> GateStackWiringComposition:
    return GateStackWiringComposition()


# --- Given -----------------------------------------------------------------


@given(parsers.parse("the feature module reached through the {subcommand} subcommand"))
def given_feature_module(wiring: GateStackWiringComposition, subcommand: str) -> None:
    wiring.given_feature_module(SPEC_BY_SUBCOMMAND[subcommand])


@given("an unknown subcommand name not in the gate-stack wiring set")
def given_unknown_subcommand(wiring: GateStackWiringComposition) -> None:
    wiring.given_unknown_subcommand(UNKNOWN_SUBCOMMAND_SPEC)


# --- When ------------------------------------------------------------------


@when("the registration of the subcommand is inspected through the real des dispatcher")
def when_inspect_registration(wiring: GateStackWiringComposition) -> None:
    wiring.when_inspecting_subcommand_registration()


@when(
    "the gate-stack reference of the module is inspected in the shipped flavor surfaces"
)
def when_inspect_reference(wiring: GateStackWiringComposition) -> None:
    wiring.when_inspecting_gate_stack_reference()


@when("the subcommand is driven end to end through the real des dispatcher")
def when_drive_subcommand(wiring: GateStackWiringComposition, tmp_path: Path) -> None:
    wiring.when_driving_the_subcommand(tmp_path)


# --- Then ------------------------------------------------------------------


@then("the subcommand is a registered des subcommand advertised with a catalog mirror")
def then_registered(wiring: GateStackWiringComposition) -> None:
    wiring.then_subcommand_is_registered()


@then(
    "the module is referenced in a flavor gate-stack so the closure scorecard sees it wired"
)
def then_referenced(wiring: GateStackWiringComposition) -> None:
    wiring.then_module_is_referenced_in_a_gate_stack()


@then("the subcommand is rejected by the dispatcher as not resolvable")
def then_rejected(wiring: GateStackWiringComposition) -> None:
    wiring.then_subcommand_is_rejected_as_not_resolvable()


@then("driving the subcommand emits a gate verdict from the existing domain logic")
def then_emits_verdict(wiring: GateStackWiringComposition) -> None:
    wiring.then_driving_emits_a_gate_verdict()
