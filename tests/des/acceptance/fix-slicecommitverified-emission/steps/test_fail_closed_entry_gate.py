"""Step definitions: fix-slicecommitverified-emission slice-02.

The carpaccio entry-gate auto-backfill FAIL-CLOSED rows -- the anti-false-allow
safety witness. Three example-based ATs at Layer 3 (subprocess/FS acceptance,
real git + real ledger on tmp_path) -- no PBT machinery (Mandate 9/11: layer-3
real-io is example-only).

Driving port (Mandate-13): the production U1 carpaccio PreToolUse intercept
`intercept_atdd_pure_dispatch`, driven through `BackfillEntryGateComposition`
(shared composition root with slice-01). Step bodies delegate to composition
methods; no inline business logic (Mandate-12 criterion 3 -- each body <=2
statements, final delegates to `composition.<method>(...)`, no control flow).

S1 step-text uniqueness (Tier-2 gate): the shared `composition` / `outcome_box`
fixtures live in `steps/conftest.py` as the single fixture SSOT (pytest resolves
conftest fixtures for every module on the path -- no duplication). pytest-bdd
binds `@given/@when/@then` bodies to the test module where `scenarios()` is
declared, so slice-02 declares its OWN step literals -- every literal is UNIQUE
within the feature dir (zero cross-file collision). The behavioural SSOT is the
shared `BackfillEntryGateComposition` methods the step bodies delegate to
(Pillar 2 via shared service vocabulary, not shared decorator strings).

The anti-false-allow KEYSTONE: each scenario asserts BOTH (a) the entering
slice is BLOCKED and (b) NO SliceCommitVerified record was appended for the
predecessor (on-disk ledger count stays 0). A gate that false-allowed on bad
evidence would fail (b).

PROBE: GREEN-regression-pins against shipped c995b66dd -- the shipped
`_attempt_predecessor_backfill` is fail-closed by construction (absent/stale
Gate-Scope -> `_verify_gate_scope` False; no commit -> `_predecessor_commit_sha`
None). They pin the existing safety against regression (ADR-028 skip-scaffolded;
GREEN on unskip).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_bdd import given, scenarios, then, when

from .domain_types import EntryGateVerdict, GateScopeSeed, SliceId


if TYPE_CHECKING:
    from .composition import BackfillEntryGateComposition, EntryGateOutcome


# The shared `composition` / `outcome_box` pytest fixtures are re-used from
# slice-01 via `steps/conftest.py` (pytest fixtures resolve through conftest --
# single source, no duplication). pytest-bdd binds step bodies to the test
# module where `scenarios()` is declared, so slice-02 declares its OWN
# `@given/@when/@then` step literals here. Every literal is UNIQUE within the
# feature dir (S1 Tier-2 gate: zero collision risk), and the shared SSOT is the
# composition root's methods the step bodies delegate to (Pillar 2 chained
# narrative via shared service vocabulary, not shared decorator strings).


scenarios("../fail-closed-entry-gate.feature")


# --- Given / When (slice-02 dispatch + drive; literal-unique) ----------------


@given(
    "the next carpaccio slice is dispatched into implementation for the fail-closed gate"
)
def given_dispatch_next_slice_fail_closed(
    composition: BackfillEntryGateComposition,
) -> None:
    composition.enter_slice(SliceId("slice-02"))


@when("the fail-closed carpaccio entry gate evaluates the dispatch")
def when_entry_gate_evaluates_fail_closed(
    composition: BackfillEntryGateComposition,
    outcome_box: dict[str, EntryGateOutcome],
) -> None:
    outcome_box["outcome"] = composition.evaluate_entry_gate()


# --- Given (slice-02 fail-closed preconditions; literal-unique) --------------


@given(
    "a carpaccio feature whose predecessor slice was committed without a recorded gate scope"
)
def given_predecessor_gate_scope_absent(
    composition: BackfillEntryGateComposition,
) -> None:
    composition.predecessor_with_bad_gate_scope(GateScopeSeed.ABSENT)


@given(
    "a carpaccio feature whose predecessor slice was committed with a stale recorded gate scope"
)
def given_predecessor_gate_scope_stale(
    composition: BackfillEntryGateComposition,
) -> None:
    composition.predecessor_with_bad_gate_scope(GateScopeSeed.STALE)


@given("a carpaccio feature whose predecessor slice was never committed")
def given_predecessor_not_committed(
    composition: BackfillEntryGateComposition,
) -> None:
    composition.predecessor_not_committed()


# --- Then (slice-02 anti-false-allow keystone; literal-unique) ---------------


@then("the entry gate refuses to verify the predecessor")
def then_predecessor_not_verified(
    composition: BackfillEntryGateComposition,
) -> None:
    assert not composition.predecessor_is_verified()


@then("no verification record for the predecessor is present in the ledger")
def then_no_record_present(composition: BackfillEntryGateComposition) -> None:
    assert composition.predecessor_verified_record_count() == 0


@then("the entry gate keeps the next slice blocked out of order")
def then_gate_keeps_blocked(outcome_box: dict[str, EntryGateOutcome]) -> None:
    assert outcome_box["outcome"].verdict is EntryGateVerdict.BLOCKED
