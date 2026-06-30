"""pytest-bdd binding for f-attest-bundled-slice slice-02 scenarios.

Driving surface (Mandate-13 driving-port-only, Layer 3 subprocess): the REAL
``des attest-bundled-slice`` subcommand via the production dispatcher, invoked
against a crafted TEMP git repo. Step bodies delegate to the composition root
(``composition_slice_02_preconditions.py``); no business logic in step bodies
(Mandate-12 criterion 3). The Given binds a fixture name to the typed
``AttestFixture`` enum (DSL emergence over typed domain vocabulary, not decorator
proliferation).

Active-RED scaffold (atdd_pure -- NOT @skip): RED until slice-02 DELIVER wires the
REUSED preconditions P1/P3/P5/P6 from ``des.cli._reverify_core`` into
``attest_bundled_slice.main()``. At HEAD the slice-01 scaffold emits
``BundledSliceAttestNotApplicable`` (exit 0) for every invocation, ignoring the
preconditions -- so each refusal/proceed Then fails with a semantic
AssertionError, never a collection / import error.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_02_preconditions import AttestPreconditionComposition
from .domain_types_attest_bundled_slice import AttestFixture


scenarios("../slice-02-reused-preconditions.feature")


@pytest.fixture
def attest(tmp_path: Path) -> AttestPreconditionComposition:
    return AttestPreconditionComposition(tmp_path)


# --- Given (one per slice-02 precondition fixture) --------------------------


@given("a bundle commit that is not an ancestor of the current head")
def given_non_ancestor(attest: AttestPreconditionComposition) -> None:
    attest.given_fixture(AttestFixture.NON_ANCESTOR)


@given("a slice that already carries a completion verification")
def given_already_verified(attest: AttestPreconditionComposition) -> None:
    attest.given_fixture(AttestFixture.ALREADY_VERIFIED)


@given("a bundle commit that is still the head with nothing burying it")
def given_still_head(attest: AttestPreconditionComposition) -> None:
    attest.given_fixture(AttestFixture.STILL_HEAD)


@given("a later slice whose predecessor carries no completion verification")
def given_predecessor_unverified(attest: AttestPreconditionComposition) -> None:
    attest.given_fixture(AttestFixture.PREDECESSOR_UNVERIFIED)


@given("a bundle slice whose preconditions all hold")
def given_all_clear(attest: AttestPreconditionComposition) -> None:
    attest.given_fixture(AttestFixture.ALL_PRECONDITIONS_CLEAR)


# --- When -------------------------------------------------------------------


@when("the maintainer attests the bundled slice")
def when_operator_attests(attest: AttestPreconditionComposition) -> None:
    attest.when_operator_attests_the_bundled_slice()


# --- Then -------------------------------------------------------------------


@then("the attestation is refused on a reused precondition")
def then_refused_on_precondition(attest: AttestPreconditionComposition) -> None:
    attest.then_attest_refuses_on_precondition()


@then("the attestation proceeds past the reused preconditions")
def then_proceeds_past_preconditions(attest: AttestPreconditionComposition) -> None:
    attest.then_attest_proceeds_past_the_preconditions()
