"""pytest-bdd binding — slice-03 (the additive Composite convergence section).

Driving port: `des feature-delta-schema verify` for the Composite checks +
`des validate-feature-delta --require-slice-plan` for the additivity-preservation
check (the EXISTING 5-column gate must stay green). Mandate-13, Layer 3 subprocess.
Each step body is a single delegation (Mandate-12).

Active-RED: at HEAD the Composite validator does not exist (scaffold raises).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition import CarpaccioPreservationComposition, VerifyComposition
from .domain_types import DocFixture


# S1 step-text-uniqueness SSOT: the `verify` fixture + the two shared verify-driving
# steps (`when "the schema gate verifies the document"`, `then "the verdict is
# pass"`) live in conftest.py — visible to every scenario in this directory with no
# per-module import, shadow-free across slice-02 and slice-03 (Mandate-12).


scenarios("../slice-03-convergence-section.feature")


@pytest.fixture
def preservation() -> CarpaccioPreservationComposition:
    return CarpaccioPreservationComposition()


# --- Given -------------------------------------------------------------------


@given("a feature-delta carrying a well-formed Architecture and Contract Tests section")
def given_good_convergence(verify: VerifyComposition, tmp_path: Path) -> None:
    verify.given_document(tmp_path, DocFixture.GOOD_CONVERGENCE)


@given("a feature-delta whose Contract-Tests sub-table header is reordered")
def given_reordered_contract_tests(verify: VerifyComposition, tmp_path: Path) -> None:
    verify.given_document(tmp_path, DocFixture.REORDERED_CONTRACT_TESTS)


@given("a feature-delta whose Architecture-Tests sub-table header is reordered")
def given_reordered_arch_tests(verify: VerifyComposition, tmp_path: Path) -> None:
    verify.given_document(tmp_path, DocFixture.REORDERED_ARCH_TESTS)


@given("a feature-delta carrying both the slice plan and the convergence section")
def given_both_sections(
    preservation: CarpaccioPreservationComposition, tmp_path: Path
) -> None:
    preservation.given_document_with_convergence(tmp_path)


# --- When --------------------------------------------------------------------
# `when "the schema gate verifies the document"` lives in shared_verify_steps.


@when("the existing slice-plan gate runs on the document")
def when_slice_plan_gate_runs(
    preservation: CarpaccioPreservationComposition,
) -> None:
    preservation.when_carpaccio_gate_runs()


# --- Then --------------------------------------------------------------------
# `then "the verdict is pass"` lives in shared_verify_steps (imported above).


@then("the verdict is fail naming the architecture-and-contract-tests section")
def then_fail_naming_convergence(verify: VerifyComposition) -> None:
    verify.then_verdict_fail_naming_offender("Architecture & Contract Tests")


@then("the five-column slice plan is still accepted")
def then_slice_plan_accepted(preservation: CarpaccioPreservationComposition) -> None:
    preservation.then_slice_plan_still_accepted()
