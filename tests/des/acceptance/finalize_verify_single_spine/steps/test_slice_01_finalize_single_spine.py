"""Step definitions: the finalize integrity gate carries exactly one spine.

f-finalize-verify-single-spine slice-01 (@walking-skeleton). Layer 2/3:
the production des verify-integrity entry, driven as a real subprocess (the
walking-skeleton wiring proof) and IN-PROCESS via main(argv) (every other
scenario). Example-only, no PBT machinery (Mandate 9/11). The verifier has a
pure-read contract: the in-process When steps assert via `assert_state_delta`
over a port-exposed filesystem universe that NO project file is mutated
(Mandate 8). Step bodies delegate to `FinalizeSpineComposition` -- no inline
business logic (Mandate-12 criterion 3).

The C3 zero-shipped scenario drives the cardinality-0 success path (a valid
ledger whose feature-end cycle ran but which ships no slice -> the done-gate's
`shipped` set is `frozenset()` -> exit 0 plain-text trace, NOT the
`FeatureReconciled` JSON of the non-empty path; ADR-027).

Active-RED scaffold (atdd_pure -- NOT @skip; ADR-025/029): the
"still asks for the classic finalize leg" scenario is RED until the REDUCE
removes the classic dispatch. On HEAD an explicit `workflow.mode: classic`
directory is routed to the classic cross-reference (exit 0, "complete DES
traces"); the scenario asserts the atdd_pure missing-ledger verdict (exit 1),
so it fails with a semantic AssertionError -- RED, not BROKEN. GREEN once the
REDUCE lands.

The legacy audit-replay reader boundary guard (the Out-of-Scope
`PhaseEventParser` do-not-touch fence) is an architectural contract, not a
port-to-port AT, so it was relocated to
`tests/des/unit/domain/test_arch_legacy_audit_replay_boundary.py` (Tier-2 S2:
no domain import at the step boundary).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .composition import FinalizeSpineComposition, VerifyResult
from .domain_types import ClassicProjectShape, IntegrityVerdict, WorkflowMode


scenarios("../slice-01-finalize-single-spine.feature")


@pytest.fixture
def composition(tmp_path: Path) -> FinalizeSpineComposition:
    return FinalizeSpineComposition(project_dir=tmp_path / "finalize")


@pytest.fixture
def box() -> dict[str, object]:
    """Carrier for the verify result across When -> Then steps."""
    return {}


# --- Given -------------------------------------------------------------------


@given(
    "a finalized atdd_pure feature whose completion ledger records the full feature-end cycle"
)
def given_full_atdd_pure(composition: FinalizeSpineComposition) -> None:
    composition.create_project()
    composition.provision_full_atdd_pure_feature()


@given(
    "a finalized atdd_pure feature whose completion ledger records the full "
    "feature-end cycle but ships no slices"
)
def given_zero_shipped_atdd_pure(composition: FinalizeSpineComposition) -> None:
    composition.create_project()
    composition.provision_zero_shipped_atdd_pure_feature()


@given("a finalize directory holding only the classic roadmap and execution log")
def given_classic_artifacts(composition: FinalizeSpineComposition) -> None:
    composition.create_project()
    composition.provision_classic_project(ClassicProjectShape.COMPLETE_TRACES)


@given("the directory still declares the classic finalize mode")
def given_explicit_classic(composition: FinalizeSpineComposition) -> None:
    composition.set_workflow_mode(WorkflowMode.CLASSIC)


@given("the directory declares no finalize mode at all")
def given_unset_mode(composition: FinalizeSpineComposition) -> None:
    composition.set_workflow_mode(WorkflowMode.UNSET)


@given("the maintainer names no finalize directory")
def given_no_target(composition: FinalizeSpineComposition) -> None:
    composition.create_project()


# --- When --------------------------------------------------------------------


@when("the maintainer runs the integrity gate on the installed spine")
def when_run_installed_spine(
    composition: FinalizeSpineComposition, box: dict[str, object]
) -> None:
    box["result"] = composition.run_on_installed_spine()


@when("the maintainer runs the integrity gate for that feature")
def when_run_for_feature(
    composition: FinalizeSpineComposition, box: dict[str, object]
) -> None:
    before = composition.capture_universe()
    box["result"] = composition.run_for_feature()
    _assert_pure_read(composition, before)


@when("the maintainer runs the integrity gate with no target")
def when_run_no_target(
    composition: FinalizeSpineComposition, box: dict[str, object]
) -> None:
    box["result"] = composition.run_with_no_target()


def _assert_pure_read(
    composition: FinalizeSpineComposition, before: dict[str, object]
) -> None:
    """Universe-bound state-delta: des verify-integrity mutates no project file."""
    assert_state_delta(
        before=before,
        after=composition.capture_universe(),
        universe={
            "roadmap.json.exists",
            "execution_log.json.exists",
            "ledger.exists",
        },
        expected={
            "roadmap.json.exists": unchanged(),
            "execution_log.json.exists": unchanged(),
            "ledger.exists": unchanged(),
        },
    )


# --- Then --------------------------------------------------------------------


def _result(box: dict[str, object]) -> VerifyResult:
    return box["result"]  # type: ignore[return-value]


@then("the integrity gate reports the feature verified")
def then_verified(box: dict[str, object]) -> None:
    assert _result(box).verdict is IntegrityVerdict.VERIFIED


@then("the integrity gate reports a missing completion ledger")
def then_missing_ledger(box: dict[str, object]) -> None:
    result = _result(box)
    # The atdd_pure missing-ledger verdict: exit 1 + a diagnostic naming the
    # absent AT-completion ledger. RED on HEAD for the explicit-classic
    # directory (the classic leg returns exit 0 + "complete DES traces").
    assert result.verdict is IntegrityVerdict.VIOLATION
    message = result.output.lower()
    assert "ledger" in message
    assert "missing" in message


@then("the integrity gate does not run the classic execution-log cross-reference")
def then_no_classic_cross_reference(box: dict[str, object]) -> None:
    # The classic cross-reference's success signature is "complete DES traces".
    # After the REDUCE that branch is gone, so the output never carries it.
    # RED on HEAD for the explicit-classic directory.
    message = _result(box).output.lower()
    assert "complete des traces" not in message


@then("the integrity gate reports a structural usage error")
def then_usage_error(box: dict[str, object]) -> None:
    assert _result(box).verdict is IntegrityVerdict.USAGE_ERROR


@then("the integrity gate reports a complete completion-ledger trace")
def then_complete_ledger_trace(box: dict[str, object]) -> None:
    # The cardinality-0 (`shipped = frozenset()`) success signature: the
    # plain-text complete-trace verdict, distinct from the non-empty-shipped
    # `FeatureReconciled` JSON event.
    message = _result(box).output.lower()
    assert "complete at-completion ledger trace" in message


@then("the integrity gate does not report any reconciled slices")
def then_no_reconciled_slices(box: dict[str, object]) -> None:
    # With zero shipped slices the verifier must NOT emit the FeatureReconciled
    # event -- that event is reserved for the non-empty-shipped reconciliation
    # path. Its absence pins the cardinality-0 branch.
    assert "featurereconciled" not in _result(box).output.lower()
