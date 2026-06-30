"""Step definitions: fix-des-e2-contract-gate-degrade-loud slice-01.

Four example-based ATs at Layer 3 (subprocess + composition acceptance, real
git + real ledger on tmp_path) -- no PBT machinery (Mandate 9/11: layer-3
real-io is example-only, sad/edge paths enumerated explicitly).

Driving ports (Mandate-13): the production ``run_contract_gate`` /
``verify_slice_commit_completeness`` CLI mains (Layer-3 subprocess) and the U1
carpaccio PreToolUse intercept ``intercept_atdd_pure_dispatch`` (Layer-3
composition), all driven through ``DegradeLoudComposition``. Step bodies
delegate to composition methods; no inline business logic (Mandate-12
criterion 3 -- each body <=2 statements, final delegates to a composition
method, no control flow).

S1 step-text uniqueness (Tier-2 gate): the shared ``composition`` /
``outcome_box`` fixtures live in ``steps/conftest.py`` as the single fixture
SSOT; every ``@given/@when/@then`` literal is UNIQUE within the feature dir.
The behavioural SSOT is the shared ``DegradeLoudComposition`` methods the step
bodies delegate to (Pillar 2 chained narrative via shared service vocabulary).

ATDD-pure active-RED (NOT @skip, ADR-025/ADR-GV-001 D6): these scenarios RUN
against the REAL production surfaces. AC-1/AC-2/AC-3 raise ``AssertionError``
at HEAD for the right reason -- the gate still hard-refuses (exit 2) on
interpreter-absence, no ``SliceCommitIndeterminate`` is minted, and the
in-order guard reads only ``SliceCommitVerified`` so it BLOCKS the successor.
AC-4 is a live-green preservation guard (the Python happy path is unchanged).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_bdd import given, scenarios, then, when

from .domain_types import EntryGateVerdict, GateOutcome, LedgerRecord


if TYPE_CHECKING:
    from .composition import DegradeLoudComposition, EntryGateOutcome


scenarios("../slice-01-des-e2-contract-gate-degrade-loud.feature")


# --- Given (preconditions; literal-unique within the feature dir) ------------


@given("a target whose contract gate cannot resolve a usable interpreter")
def given_target_without_interpreter(composition: DegradeLoudComposition) -> None:
    # No substrate mutation -- the interpreter-absence is forced at drive time
    # by the production-resolver monkeypatch inside the subprocess driver.
    assert composition is not None


@given("the predecessor slice carries an indeterminate slice-commit record")
def given_predecessor_indeterminate_record(
    composition: DegradeLoudComposition,
) -> None:
    composition.seed_predecessor_indeterminate_record()


@given("a target whose contract gate can resolve a usable interpreter")
def given_target_with_interpreter(composition: DegradeLoudComposition) -> None:
    # The running interpreter resolves pytest; no forcing -- AC-4 preservation.
    assert composition is not None


# --- When (drive the real production ports; literal-unique) ------------------


@when("the contract gate runs for the slice")
def when_contract_gate_runs(composition: DegradeLoudComposition) -> None:
    composition.drive_run_contract_gate_without_interpreter()


@when("verify-slice-commit runs the exit gate for the slice")
def when_verify_slice_commit_runs_indeterminate(
    composition: DegradeLoudComposition,
) -> None:
    composition.drive_verify_slice_commit_without_interpreter()


@when("the next carpaccio slice is dispatched into implementation")
def when_next_slice_dispatched(
    composition: DegradeLoudComposition,
    outcome_box: dict[str, EntryGateOutcome],
) -> None:
    outcome_box["outcome"] = composition.drive_in_order_guard_for_successor()


@when("verify-slice-commit runs the exit gate for the slice with the gate passing")
def when_verify_slice_commit_runs_passing(
    composition: DegradeLoudComposition,
) -> None:
    composition.drive_verify_slice_commit_with_interpreter()


# --- Then (assert observable shipped artifacts; literal-unique) --------------


@then("the contract gate reports an indeterminate outcome")
def then_gate_indeterminate(composition: DegradeLoudComposition) -> None:
    assert composition.observed_gate_outcome() is GateOutcome.INDETERMINATE


@then("the contract gate does not hard-refuse the slice")
def then_gate_not_hard_refuse(composition: DegradeLoudComposition) -> None:
    assert composition.gate_returncode() != 2


@then("the completion ledger gains an indeterminate slice-commit record")
def then_ledger_has_indeterminate(composition: DegradeLoudComposition) -> None:
    assert composition.ledger_has_record(LedgerRecord.SLICE_COMMIT_INDETERMINATE)


@then("the completion ledger gains no verified slice-commit record")
def then_ledger_has_no_verified(composition: DegradeLoudComposition) -> None:
    assert not composition.ledger_has_record(LedgerRecord.SLICE_COMMIT_VERIFIED)


@then("the carpaccio in-order guard clears the next slice to enter")
def then_in_order_guard_clears(outcome_box: dict[str, EntryGateOutcome]) -> None:
    assert outcome_box["outcome"].verdict is EntryGateVerdict.ALLOWED


@then("the completion ledger gains a verified slice-commit record")
def then_ledger_has_verified(composition: DegradeLoudComposition) -> None:
    assert composition.ledger_has_record(LedgerRecord.SLICE_COMMIT_VERIFIED)


@then("verify-slice-commit reports success")
def then_verify_reports_success(composition: DegradeLoudComposition) -> None:
    assert composition.gate_returncode() == 0
