"""Step definitions: the byte-stable DELIVER-entry migration regression-witness
(algebra-projections-enforced slice-02, DISCUSS WD-2, DESIGN DA-3/DD-A3, ADR-001
D2).

Layer 3 (subprocess/FS acceptance). Example-only, no PBT machinery (Mandate 9/11).

These scenarios drive the REAL DELIVER-entry contract-freeze gate
(``des verify-deliver-entry-contract``), which is REGISTERED AND FUNCTIONAL at HEAD
(it shipped in f-deliver-entry-contract-freeze). They are therefore a REGRESSION
WITNESS, not an active-RED scaffold: they PASS at HEAD (the pre-migration gate) and
MUST stay green through the DELIVER slice-02 registry migration. They go RED only if
the migration breaks the byte-stable observable contract — that is their entire
purpose (the un-gameable proof of ADR-001 ADD-not-mutate / DA-3).

The byte-stability oracle (``then_refusal_names_the_four_locked_sections``) asserts
the FAIL diagnostic NAMES all four legacy locked sections (Architecture & Contract
Tests / ADR Refs / Reuse Analysis / Slice Plan). A naive swap to the 1-entry
deliver.yaml output_contract would shrink the named set to ``Slice Plan`` only and
trip this witness — exactly the silent-substrate-mutation the WD-2 marchiato rule
forbids.

Step bodies delegate to ``DeliverEntryByteStableComposition``; no inline business
logic (Mandate-12 criterion 3).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_02 import DeliverEntryByteStableComposition
from .domain_types_slice_02 import (
    DELIVER_ENTRY_SHAPE_BY_PHRASE,
    FreezeVerdict,
)


scenarios("../slice-02-deliver-entry-byte-stable-migration.feature")


@pytest.fixture
def deliver_entry_composition() -> DeliverEntryByteStableComposition:
    """Production-wired composition root driving the real verify-deliver-entry CLI."""
    return DeliverEntryByteStableComposition()


# --- Given -------------------------------------------------------------------


@given(parsers.parse("a DELIVER-entry contract {shape_phrase}"))
def given_deliver_entry_contract(
    deliver_entry_composition: DeliverEntryByteStableComposition, shape_phrase: str
) -> None:
    deliver_entry_composition.given_contract_shape(
        DELIVER_ENTRY_SHAPE_BY_PHRASE[shape_phrase]
    )


# --- When --------------------------------------------------------------------


@when("the contract-freeze gate runs at the DELIVER gate-IN")
def when_freeze_gate_runs(
    deliver_entry_composition: DeliverEntryByteStableComposition, tmp_path: Path
) -> None:
    deliver_entry_composition.when_the_freeze_gate_runs_at_deliver_entry(tmp_path)


# --- Then --------------------------------------------------------------------


@then("the freeze gate refuses the contract for a missing locked section")
def then_refuses(
    deliver_entry_composition: DeliverEntryByteStableComposition,
) -> None:
    deliver_entry_composition.then_verdict_is(FreezeVerdict.FAIL)


@then("the refusal names the four locked sections of the DELIVER-entry contract")
def then_names_four(
    deliver_entry_composition: DeliverEntryByteStableComposition,
) -> None:
    deliver_entry_composition.then_refusal_names_the_four_locked_sections()


@then("the freeze gate leaves the contract unfrozen")
def then_unfrozen(
    deliver_entry_composition: DeliverEntryByteStableComposition,
) -> None:
    deliver_entry_composition.then_contract_unfrozen()


@then("the freeze gate freezes the contract")
def then_freezes(
    deliver_entry_composition: DeliverEntryByteStableComposition,
) -> None:
    deliver_entry_composition.then_verdict_is(FreezeVerdict.PASS)


@then("the freeze gate emits no diagnostic")
def then_no_diagnostic(
    deliver_entry_composition: DeliverEntryByteStableComposition,
) -> None:
    deliver_entry_composition.then_no_diagnostic()
