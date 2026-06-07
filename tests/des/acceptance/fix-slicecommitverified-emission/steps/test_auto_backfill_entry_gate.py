"""Step definitions: fix-slicecommitverified-emission slice-01.

The carpaccio entry-gate auto-backfill happy path. Three example-based ATs at
Layer 3 (subprocess/FS acceptance, real git + real ledger on tmp_path) --
no PBT machinery (Mandate 9/11: layer-3 real-io is example-only).

Driving port (Mandate-13): the production U1 carpaccio PreToolUse intercept
`intercept_atdd_pure_dispatch`, driven through `BackfillEntryGateComposition`.
Step bodies delegate to composition methods; no inline business logic
(Mandate-12 criterion 3 -- each body <=2 statements, final delegates to
`composition.<method>(...)`, no control flow).

RED contract: `_carpaccio_order_block` is a pure read on master -- it blocks
`CarpaccioSliceOutOfOrder` rather than running the verify-then-record backfill.
Every scenario fails RED for MISSING_FUNCTIONALITY (xfail-strict via conftest
until slice-01 GREEN ships the `_attempt_predecessor_backfill` branch).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_bdd import given, scenarios, then, when

from .domain_types import EntryGateVerdict, PredecessorLedgerState, SliceId


if TYPE_CHECKING:
    from .composition import BackfillEntryGateComposition, EntryGateOutcome


scenarios("../auto-backfill-entry-gate.feature")


# The `composition` / `outcome_box` fixtures are the shared SSOT in
# `steps/conftest.py` (single source for slice-01 + slice-02; pytest resolves
# conftest fixtures for every module on the path).


# --- Given ------------------------------------------------------------------


@given(
    "a carpaccio feature whose predecessor slice was committed but never recorded as verified"
)
def given_predecessor_committed_unrecorded(
    composition: BackfillEntryGateComposition,
) -> None:
    composition.predecessor_in_state(PredecessorLedgerState.COMMITTED_BUT_UNRECORDED)


@given(
    "a carpaccio feature whose predecessor slice was committed and already recorded as verified"
)
def given_predecessor_committed_recorded(
    composition: BackfillEntryGateComposition,
) -> None:
    composition.predecessor_in_state(PredecessorLedgerState.COMMITTED_AND_RECORDED)


@given("the acceptance designer dispatches the next slice into implementation")
def given_dispatch_next_slice(composition: BackfillEntryGateComposition) -> None:
    composition.enter_slice(SliceId("slice-02"))


# --- When -------------------------------------------------------------------


@when("the carpaccio entry gate evaluates the dispatch")
def when_entry_gate_evaluates(
    composition: BackfillEntryGateComposition,
    outcome_box: dict[str, EntryGateOutcome],
) -> None:
    outcome_box["outcome"] = composition.evaluate_entry_gate()


# --- Then -------------------------------------------------------------------


@then("the entry gate auto-verifies the predecessor and records it")
def then_predecessor_auto_verified(
    composition: BackfillEntryGateComposition,
) -> None:
    assert composition.predecessor_is_verified()


@then("the entry gate allows the next slice in")
def then_gate_allows(outcome_box: dict[str, EntryGateOutcome]) -> None:
    assert outcome_box["outcome"].verdict is EntryGateVerdict.ALLOWED


@then("exactly one verification record for the predecessor is present in the ledger")
def then_exactly_one_record(composition: BackfillEntryGateComposition) -> None:
    assert composition.predecessor_verified_record_count() == 1


@then("the predecessor is now recorded as verified")
def then_predecessor_recorded(composition: BackfillEntryGateComposition) -> None:
    assert composition.predecessor_is_verified()


@then("no additional verification record for the predecessor is added to the ledger")
def then_no_duplicate_record(composition: BackfillEntryGateComposition) -> None:
    assert composition.predecessor_verified_record_count() == 1
