"""Step definitions: slice-03 -- the M7 AT-completion ledger substrate.

slice-03 of F-DES-ATDD-PURE-HOOK-GATES (U3 -- ADR-030 D3 / M7).

Three ATs, max PBT + parametrize density (feedback_ats_max_pbt_parametrize_
density_2026_05_19):
  * walking-skeleton (@wiring_e2e) -- 1 example-based scenario: record gate
    events into a real ledger file, integrity-read it back, reconstruct slice
    state. Genuine FS round-trip, not fixture-folded.
  * corruption Scenario Outline -- 1 parametrized AT collapsing the M7
    integrity-violation universe (well-formed / malformed / truncated /
    hash-mismatch / seq-gap) into a single fail-closed decision table.
  * provisioning scenario -- the M11 mkdir(exist_ok=True) + EAFP append.

Layer 3 (subprocess/FS acceptance, real ledger file on tmp_path) -- example-only
sad paths, no PBT machinery (Mandate 9/11). Step bodies delegate to
`LedgerComposition`; no inline logic (Mandate-12 criterion 3).

RED contract: the production module
`des.adapters.driven.logging.at_completion_ledger` does not exist on master --
the composition import fails, every scenario fails RED for MISSING_FUNCTIONALITY.
slice-03 GREEN ships the real `AtCompletionLedger` substrate.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition import LedgerComposition, ReadOutcome
from .domain_types import (
    CORRUPTION_BY_PHRASE,
    GATE_EVENT_BY_PHRASE,
    VERDICT_BY_PHRASE,
    SliceId,
)


scenarios("../at-completion-ledger.feature")


@pytest.fixture
def composition(tmp_path: Path) -> LedgerComposition:
    """Production-wired ledger composition root rooted at a tmp project dir."""
    return LedgerComposition(tmp_path)


@pytest.fixture
def outcome_box() -> dict[str, ReadOutcome]:
    """Carrier for the integrity-checked read outcome."""
    return {}


def _outcome(outcome_box: dict[str, ReadOutcome]) -> ReadOutcome:
    return outcome_box["outcome"]


# --- Given -------------------------------------------------------------------


@given("a fresh AT-completion ledger for an atdd_pure feature")
def given_fresh_ledger(composition: LedgerComposition) -> None:
    composition.use_fresh_ledger()


@given("an AT-completion ledger with three recorded gate events")
def given_three_events(composition: LedgerComposition) -> None:
    composition.record_three_events()


@given(parsers.parse("the ledger has been corrupted with {corruption}"))
def given_corruption(composition: LedgerComposition, corruption: str) -> None:
    composition.corrupt_ledger(CORRUPTION_BY_PHRASE[corruption])


@given("an atdd_pure feature whose ledger directory does not yet exist")
def given_unprovisioned(composition: LedgerComposition) -> None:
    composition.use_unprovisioned_feature()


# --- When --------------------------------------------------------------------


@when(parsers.parse("{gate_event} is recorded for {slice_id}"))
def when_record_event(
    composition: LedgerComposition, gate_event: str, slice_id: str
) -> None:
    composition.record_gate_event(GATE_EVENT_BY_PHRASE[gate_event], SliceId(slice_id))


@when("the ledger is read under the integrity contract")
def when_read_integrity(
    composition: LedgerComposition, outcome_box: dict[str, ReadOutcome]
) -> None:
    outcome_box["outcome"] = composition.read_under_integrity_contract()


# --- Then --------------------------------------------------------------------


@then("the integrity-checked read of the ledger succeeds")
def then_read_succeeds(
    composition: LedgerComposition, outcome_box: dict[str, ReadOutcome]
) -> None:
    outcome_box["outcome"] = composition.read_under_integrity_contract()
    assert _outcome(outcome_box).verdict == VERDICT_BY_PHRASE["succeeds"]


@then(parsers.parse("the integrity-checked read verdict is {verdict}"))
def then_read_verdict(outcome_box: dict[str, ReadOutcome], verdict: str) -> None:
    assert _outcome(outcome_box).verdict == VERDICT_BY_PHRASE[verdict]


@then(parsers.parse("the ledger reports a verified slice commit for {slice_id}"))
def then_reports_verified(outcome_box: dict[str, ReadOutcome], slice_id: str) -> None:
    assert slice_id in _outcome(outcome_box).verified_slices


@then(
    parsers.parse("the ledger does not report a verified slice commit for {slice_id}")
)
def then_not_reports_verified(
    outcome_box: dict[str, ReadOutcome], slice_id: str
) -> None:
    assert slice_id not in _outcome(outcome_box).verified_slices


@then("every ledger record carries a gap-free monotonic sequence number")
def then_seq_gap_free(outcome_box: dict[str, ReadOutcome]) -> None:
    assert _outcome(outcome_box).seq_gap_free


@then("every ledger record carries a record hash over its own fields")
def then_every_record_hashed(outcome_box: dict[str, ReadOutcome]) -> None:
    assert _outcome(outcome_box).every_record_hashed


@then("the ledger directory is provisioned and the record is appended")
def then_dir_provisioned(composition: LedgerComposition) -> None:
    assert composition.ledger_directory_exists()
