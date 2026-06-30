"""pytest-bdd binding for f-attest-bundled-slice slice-04 scenarios (gates + ledger).

Driving surface (Mandate-13 driving-port-only, Layer 3 subprocess): the REAL
``des attest-bundled-slice`` subcommand via the production dispatcher, invoked
against a crafted TEMP git repo whose bundle slice's ATs genuinely pass/fail.
Step bodies delegate to the composition root
(``composition_slice_04_gate_and_ledger.py``); no business logic in step bodies
(Mandate-12 criterion 3). The Given binds a fixture name to the typed
``GateOutcomeFixture`` enum (DSL emergence over typed domain vocabulary). The
ledger assertions read the ledger ``.jsonl`` FILE as data -- ZERO ``des.adapters.*``
import (slice-02 RC-2 / F-005).

Active-RED scaffold (atdd_pure -- NOT @skip): RED until slice-04 DELIVER replaces
the post-A2 ``BundledSliceAttestPreconditionsCleared`` placeholder in
``attest_bundled_slice.main()`` with the gate composition (E1+E2 via the REUSED
``_compose_gates``) and the ledger emit (via the REUSED ``_record_outcome``). At
HEAD main() stops at the placeholder (exit 0), running NO gates and touching NO
ledger. Each Then turns a captured subprocess observable OR a ledger-file read
into a semantic AssertionError, never a collection / import error.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_04_gate_and_ledger import GateAndLedgerComposition
from .domain_types_attest_bundled_slice import GateOutcomeFixture


scenarios("../slice-04-gate-composition-and-ledger.feature")


@pytest.fixture
def attest(tmp_path: Path) -> GateAndLedgerComposition:
    return GateAndLedgerComposition(tmp_path)


# --- Given (one per slice-04 gate-outcome fixture) --------------------------


@given("a bundle commit whose contract suite is red on HEAD")
def given_red_contract_suite(attest: GateAndLedgerComposition) -> None:
    attest.given_fixture(GateOutcomeFixture.RED_CONTRACT_SUITE)


@given("a bundle commit carrying the slice's green acceptance test and production work")
def given_green_bundle_slice(attest: GateAndLedgerComposition) -> None:
    attest.given_fixture(GateOutcomeFixture.GREEN_BUNDLE_SLICE)


# --- When -------------------------------------------------------------------


@when("the maintainer attests the bundled slice")
def when_operator_attests(attest: GateAndLedgerComposition) -> None:
    attest.when_operator_attests_the_bundled_slice()


# --- Then -------------------------------------------------------------------


@then("the attestation is blocked and the slice gains no verification record")
def then_blocked_no_verification(attest: GateAndLedgerComposition) -> None:
    attest.then_attest_blocked_and_no_verification()


@then("the slice gains a verification record in the completion ledger")
def then_gains_verification(attest: GateAndLedgerComposition) -> None:
    attest.then_slice_gains_a_verification_record()


@then(
    "the bundle attestation is recorded with the maintainer's reason and the bundle commit"
)
def then_provenance_recorded(attest: GateAndLedgerComposition) -> None:
    attest.then_provenance_record_carries_reason_and_commit()


@then("the closure scorecard counts the slice as delivered")
def then_scorecard_counts(attest: GateAndLedgerComposition) -> None:
    attest.then_scorecard_counts_the_slice_as_delivered()
