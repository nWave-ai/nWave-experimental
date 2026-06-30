"""pytest-bdd binding — slice-02 (the three pure projections).

Driving port: `des feature-delta-schema {verify,inject,contract}` subprocesses
(Mandate-13, Layer 3). P1 verify ATs arrange a real feature-delta `.md` in a
hermetic tmp_path. Each step body is a single delegation (Mandate-12).

Active-RED: at HEAD the scaffold raises, so each projection subcommand exits
non-zero and the `then` assertions fail for the right reason.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition import (
    ContractComposition,
    InjectComposition,
    VerifyComposition,
)
from .domain_types import DocFixture, Wave


# S1 step-text-uniqueness SSOT: the `verify` fixture + the two shared verify-driving
# steps (`when "the schema gate verifies the document"`, `then "the verdict is
# pass"`) live in conftest.py — visible to every scenario in this directory with no
# per-module import, shadow-free across slice-02 and slice-03 (Mandate-12).


scenarios("../slice-02-three-projections.feature")


@pytest.fixture
def inject() -> InjectComposition:
    return InjectComposition()


@pytest.fixture
def contract() -> ContractComposition:
    return ContractComposition()


# --- Given -------------------------------------------------------------------


@given("a well-formed feature-delta document")
def given_well_formed(verify: VerifyComposition, tmp_path: Path) -> None:
    verify.given_document(tmp_path, DocFixture.WELL_FORMED)


@given("a feature-delta whose slice-plan table header is reordered")
def given_bad_slice_plan(verify: VerifyComposition, tmp_path: Path) -> None:
    verify.given_document(tmp_path, DocFixture.BAD_SLICE_PLAN)


@given("a feature-delta document that cannot be decoded")
def given_unreadable(verify: VerifyComposition, tmp_path: Path) -> None:
    verify.given_document(tmp_path, DocFixture.UNREADABLE)


# --- When --------------------------------------------------------------------
# `when "the schema gate verifies the document"` lives in shared_verify_steps
# (imported above) — registered once, no cross-file shadow.


@when("the schema injects sections for the distill wave")
def when_inject_distill(inject: InjectComposition) -> None:
    inject.when_injected(Wave.DISTILL)


@when(
    "the maintainer requests the write contract for the "
    "architecture-and-contract-tests section"
)
def when_contract_requested(contract: ContractComposition) -> None:
    contract.when_contract_requested("architecture-and-contract-tests")


# --- Then --------------------------------------------------------------------
# `then "the verdict is pass"` lives in shared_verify_steps (imported above).


@then("the verdict is fail naming the slice-plan section")
def then_fail_naming_slice_plan(verify: VerifyComposition) -> None:
    verify.then_verdict_fail_naming_offender("Slice Plan")


@then("the verdict is indeterminate and never a silent pass")
def then_indeterminate(verify: VerifyComposition) -> None:
    verify.then_verdict_indeterminate()


@then("the projected rows are exactly the sections whose consumed-by includes distill")
def then_inject_distill_rows(inject: InjectComposition) -> None:
    inject.then_rows_all_consume_wave()


@then("the write spec carries the section's heading literal")
def then_write_spec_heading(contract: ContractComposition) -> None:
    contract.then_returns_write_spec(
        "## Wave: DESIGN / [REF] Architecture & Contract Tests"
    )
