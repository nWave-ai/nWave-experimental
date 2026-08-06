"""Step definitions: des-verify-integrity respects the project's workflow mode.

ADR-028 D4.2 / slice-02 of the ATDD-pure rollout.

Layer 2 (component: driving port invoked in-process via main(argv) under
redirect_stdout, real FS on tmp_path). Example-only, no PBT machinery
(Mandate 9/11). The verifier has a pure-read contract: the one state-observing
step asserts via `assert_state_delta` over a port-exposed filesystem universe
that NO project file is mutated (Mandate 8).

Step bodies delegate to `VerifyIntegrityComposition`; no inline business logic
(Mandate-12 criterion 3) -- each body is a typed lookup plus a composition call.

Regression contract: the atdd_pure scenarios specify one ledger-driven spine.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .composition import VerifyIntegrityComposition, VerifyIntegrityResult
from .domain_types import (
    FeatureId,
    IntegrityVerdict,
    LedgerState,
    WorkflowMode,
)


scenarios("../verify-integrity-mode-aware.feature")


@pytest.fixture
def composition(tmp_path: Path) -> VerifyIntegrityComposition:
    """Production-wired composition root over a tmp_path deliver project."""
    return VerifyIntegrityComposition(project_dir=tmp_path / "deliver")


@pytest.fixture
def result_box() -> dict[str, VerifyIntegrityResult]:
    """Carrier for the des-verify-integrity result across When -> Then steps."""
    return {}


# --- Given -------------------------------------------------------------------


@given(parsers.parse('a deliver project directory for feature "{feature_id}"'))
def given_project(composition: VerifyIntegrityComposition, feature_id: str) -> None:
    composition.create_project(FeatureId(feature_id))


@given(parsers.parse('the project workflow mode is "{mode}"'))
def given_workflow_mode(composition: VerifyIntegrityComposition, mode: str) -> None:
    composition.set_workflow_mode(WorkflowMode(mode))


@given("the AT-completion ledger is present with every slice shipped")
def given_ledger_present(composition: VerifyIntegrityComposition) -> None:
    composition.provision_ledger(LedgerState.PRESENT_ALL_SHIPPED)


@given("the AT-completion ledger is absent")
def given_ledger_absent(composition: VerifyIntegrityComposition) -> None:
    composition.provision_ledger(LedgerState.ABSENT)


# --- When --------------------------------------------------------------------


@when("the operator runs des-verify-integrity for that feature")
def when_run_verify_integrity(
    composition: VerifyIntegrityComposition,
    result_box: dict[str, VerifyIntegrityResult],
) -> None:
    before = composition.capture_universe()
    result_box["result"] = composition.run_verify_integrity()
    _assert_pure_read(composition, before)


def _assert_pure_read(
    composition: VerifyIntegrityComposition,
    before: dict[str, object],
) -> None:
    """Universe-bound state-delta: des-verify-integrity mutates no project file.

    The verifier reads the ledger and must never create or delete it.
    """
    assert_state_delta(
        before=before,
        after=composition.capture_universe(),
        universe={
            "ledger.exists",
        },
        expected={
            "ledger.exists": unchanged(),
        },
    )


# --- Then --------------------------------------------------------------------


@then("des-verify-integrity reports the feature verified")
def then_verified(result_box: dict[str, VerifyIntegrityResult]) -> None:
    assert result_box["result"].verdict is IntegrityVerdict.VERIFIED


@then("des-verify-integrity reports an integrity violation")
def then_violation(result_box: dict[str, VerifyIntegrityResult]) -> None:
    assert result_box["result"].verdict is IntegrityVerdict.VIOLATION


@then("the diagnostic message names the missing AT-completion ledger")
def then_diagnostic_names_ledger(
    result_box: dict[str, VerifyIntegrityResult],
) -> None:
    message = result_box["result"].output.lower()
    assert "ledger" in message


@then("des-verify-integrity does not crash")
def then_no_crash(result_box: dict[str, VerifyIntegrityResult]) -> None:
    # A crash would surface as an uncaught exception before `result` is set,
    # or as the argparse usage-error exit code 2. A graceful diagnostic is
    # exit 1 (VIOLATION) with a non-empty message.
    result = result_box["result"]
    assert result.verdict is not IntegrityVerdict.USAGE_ERROR
    assert result.output.strip() != ""
