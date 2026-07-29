"""Step definitions for slice-02 — installed operator clears the carpaccio gate.

Mandate-12 criterion 3: every step body is a typed lookup plus one composition
call (no control flow, no inline business logic). The composition root
(composition.py) is the single source of truth for behaviour.

S1 (step-text uniqueness): every literal step string here is unique within the
feature directory — slice-01 uses distinct literals (see
steps_slice_01_producer_ships.py).
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, then, when

from .composition import GateDecision, ShippingComposition
from .domain_types import ReviewOutcome


@pytest.fixture()
def installed(tmp_path, request) -> ShippingComposition:
    """Production-wired composition root with an installed-shape sandbox.

    The repo root supplies the importable source tree; the tmp_path sandbox is
    the installed instance whose working repository has NO enclosing repository
    above it.
    """
    repo_root = request.config.rootpath
    return ShippingComposition(repo_dir=repo_root, installed_root=tmp_path)


# --- Given (Background + per-scenario) ---------------------------------------


@given(
    "an installed instance with no enclosing repository and an empty AT-completion ledger"
)
def given_installed_instance_empty_ledger(installed: ShippingComposition) -> None:
    installed.provision_installed_instance_with_empty_ledger()


@given("the operator points the recorder at the working repository explicitly")
def given_operator_points_at_working_repo(installed: ShippingComposition) -> None:
    return None


@given(
    "the operator has recorded an approved AT-review verdict from the installed instance"
)
def given_operator_recorded_approval(installed: ShippingComposition) -> None:
    installed.record_verdict_from_installed_instance(ReviewOutcome.APPROVED)


# --- When ---------------------------------------------------------------------


@when("the operator records an approved AT-review verdict from the installed instance")
def when_operator_records_approval(installed: ShippingComposition) -> None:
    installed.record_verdict_from_installed_instance(ReviewOutcome.APPROVED)


@when(
    "the operator records a needs-revision AT-review verdict from the installed instance",
    target_fixture="record_result",
)
def when_operator_records_needs_revision(installed: ShippingComposition):
    return installed.record_verdict_from_installed_instance(
        ReviewOutcome.NEEDS_REVISION
    )


@when(
    "the operator runs the carpaccio gate for that slice from the installed instance",
    target_fixture="gate_decision",
)
def when_operator_runs_gate(installed: ShippingComposition) -> GateDecision:
    return installed.run_carpaccio_gate_from_installed_instance()


@when(
    "the operator records an approved AT-review verdict standing in the working "
    "repository with no repository pointer"
)
def when_operator_records_approval_from_cwd(installed: ShippingComposition) -> None:
    installed.record_verdict_from_working_repo_cwd(ReviewOutcome.APPROVED)


# --- Then ---------------------------------------------------------------------


@then("the working repository's ledger gains one AT-review verdict for the slice")
def then_ledger_gains_one_verdict(installed: ShippingComposition) -> None:
    assert len(installed.verdicts_for_entering_slice()) == 1


@then(
    "the recorded verdict binds the reviewer identity and the content seal "
    "it was reviewed under"
)
def then_record_binds_reviewer_and_seal(installed: ShippingComposition) -> None:
    # Keyless equal-or-stronger replacement for the superseded HMAC-verifies
    # assertion (oss-review-verdict-demotion S2): the record's PRESENT fields
    # are the whole control — APPROVED verdict, named reviewer, AT-set binding,
    # content seal, timestamp.
    assert installed.latest_record_binds_reviewer_and_seal()


@then("the recorded verdict carries no signature field and needed no key")
def then_record_is_keyless(installed: ShippingComposition) -> None:
    assert not installed.latest_record_carries_signature_field()


@then("the carpaccio gate clears the slice")
def then_gate_clears(gate_decision: GateDecision) -> None:
    assert gate_decision is GateDecision.CLEARED


@then("the installed recorder completes the recording cleanly")
def then_recorder_completes_cleanly(record_result) -> None:
    assert record_result.exit_code == 0, record_result.stderr


@then("the recorded verdict is not an approval")
def then_recorded_verdict_is_not_approval(installed: ShippingComposition) -> None:
    assert installed.latest_record_is_not_approval()


@then("the carpaccio gate refuses to clear the slice")
def then_gate_refuses(installed: ShippingComposition) -> None:
    assert (
        installed.run_carpaccio_gate_from_installed_instance() is GateDecision.REFUSED
    )
