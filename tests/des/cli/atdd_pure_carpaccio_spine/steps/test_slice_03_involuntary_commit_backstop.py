"""Step definitions -- slice-03: M-2 involuntary backstop + DDD-10 reconciliation.

F-SIMPLIFY-ATDD-PURE-CARPACCIO-SPINE slice-03 (@coupled). Layer 3 (subprocess /
FS acceptance): the M-2 pre-commit hook (verify_slice_ledger_record.py) and the
verify_deliver_integrity CLI are the driving ports; the AT-completion ledger and
git history (read-only) are the driven ports. Example-based sad paths
(Mandate 11).

Shares ``CarpaccioSpineComposition`` (Pillar 3). Step bodies delegate; no inline
logic (Mandate-12 criterion 3). RED-by-design held green via the suite
``conftest.py`` ``xfail(strict=True)`` mechanism.

Two driving ports, two decision-table Scenario Outlines (max-PBT/parametrize-
density standing rule):

* The M-2 backstop is an allow / refuse / abstain decision table over a commit's
  ledger record. The abstain row -- an ordinary commit with no slice-id trailer
  -- is the hook's DOMINANT path: the hook fires on EVERY commit repo-wide, and
  must wave an ordinary commit through cleanly (``NotASliceCommit``, exit 0), or
  every developer's every commit is rejected and the repo is bricked.
* The DDD-10 reconciliation is a reconciled / unreconciled sweep. The reconciled
  row witnesses the success verdict (``FeatureReconciled``, exit 0) -- DDD-10's
  authoritative feature-close PASS.

Non-blocking-review reconciliation (recorded here for the crafter): the M-2
backstop is an EARLY-WARNING control fired at commit time; DDD-10
verify_deliver_integrity is the AUTHORITATIVE feature-close sweep. When both run,
M-2 catches first. When M-2 is bypassed (--no-verify, a foreign commit path),
DDD-10 still catches the unrecorded slice at feature close -- the reconciliation
Outline's ``unreconciled`` row exercises exactly the M-2-absent / DDD-10-catches
case.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition import CarpaccioSpineComposition
from .domain_types import (
    COMMIT_BACKSTOP_OUTCOME_BY_PHRASE,
    INTEGRITY_OUTCOME_BY_PHRASE,
    CommitBackstopOutcome,
    FeatureId,
    IntegrityOutcome,
)


scenarios("../slice-03-involuntary-commit-backstop.feature")


@pytest.fixture
def composition(tmp_path: Path) -> CarpaccioSpineComposition:
    return CarpaccioSpineComposition(project_root=tmp_path / "project")


@pytest.fixture
def result_box() -> dict[str, object]:
    return {}


# --- Given -------------------------------------------------------------------


@given("a feature project with a multi-slice plan")
def given_feature_project(composition: CarpaccioSpineComposition) -> None:
    composition.create_feature_project(FeatureId("acceptance-fixture-feature"))


@given("a slice commit exists for the entering slice")
def given_slice_commit(composition: CarpaccioSpineComposition) -> None:
    composition.create_slice_commit()


@given(parsers.parse("the commit under inspection is {commit}"))
def given_backstop_commit(composition: CarpaccioSpineComposition, commit: str) -> None:
    composition.arrange_backstop_commit(COMMIT_BACKSTOP_OUTCOME_BY_PHRASE[commit])


@given(parsers.parse("a feature where {ledger_state}"))
def given_reconciliation_feature(
    composition: CarpaccioSpineComposition, ledger_state: str
) -> None:
    composition.arrange_reconciliation_feature(
        INTEGRITY_OUTCOME_BY_PHRASE[ledger_state]
    )


# --- When --------------------------------------------------------------------


@when("the commit-time backstop inspects the commit")
def when_backstop_inspects(
    composition: CarpaccioSpineComposition, result_box: dict[str, object]
) -> None:
    result_box["before"] = composition.capture_universe()
    result_box["result"] = composition.run_commit_backstop_hook(
        composition.backstop_commit_message
    )
    result_box["after"] = composition.capture_universe()


@when("the orchestrator runs the feature-end reconciliation")
def when_run_reconciliation(
    composition: CarpaccioSpineComposition, result_box: dict[str, object]
) -> None:
    result_box["before"] = composition.capture_universe()
    result_box["result"] = composition.run_verify_deliver_integrity()
    result_box["after"] = composition.capture_universe()


# --- Then --------------------------------------------------------------------


@then(parsers.parse('the commit-time backstop reaches the verdict "{verdict}"'))
def then_backstop_verdict(
    composition: CarpaccioSpineComposition,
    result_box: dict[str, object],
    verdict: str,
) -> None:
    result = result_box["result"]
    assert "Traceback (most recent call last)" not in result.stderr, (
        f"the backstop crashed rather than reaching a verdict "
        f"(exit {result.exit_code}); stderr:\n{result.stderr}"
    )
    # Classify on the port-exposed JSON event, not the exit code -- a missing
    # hook or an argparse usage error exits non-zero but emits no event, so a
    # genuine refusal cannot be impersonated. Honestly RED until the hook ships.
    observed = composition.observed_backstop_outcome(result)
    expected = CommitBackstopOutcome(verdict)
    assert observed == expected, (
        f"expected the backstop to reach {expected.value!r}; got {observed!r}, "
        f"exit {result.exit_code}: {result.stderr or result.stdout}"
    )


@then(parsers.parse('the feature-end reconciliation reaches the outcome "{outcome}"'))
def then_reconciliation_outcome(
    composition: CarpaccioSpineComposition,
    result_box: dict[str, object],
    outcome: str,
) -> None:
    result = result_box["result"]
    assert "Traceback (most recent call last)" not in result.stderr, (
        f"reconciliation crashed rather than reaching an outcome "
        f"(exit {result.exit_code}); stderr:\n{result.stderr}"
    )
    observed = composition.observed_integrity_outcome(result)
    expected = IntegrityOutcome(outcome)
    assert observed == expected, (
        f"expected the reconciliation to reach {expected.value!r}; got "
        f"{observed!r}, exit {result.exit_code}: {result.stderr or result.stdout}"
    )


@then("the system filesystem is otherwise unchanged")
def then_filesystem_unchanged(result_box: dict[str, object]) -> None:
    # verify_deliver_integrity is a read-only reconciliation: bounded-change
    # contract -- the bounded observable asserted here is "the ledger record set
    # is not appended to" (verified-slice count unchanged across the run). This
    # is NOT an unbounded-preservation proof (no whole-tree hash snapshot) --
    # the honest shape is bounded-change over the port-exposed ledger observable.
    before = result_box["before"]
    after = result_box["after"]
    assert (
        after["ledger.slice_commit_verified_count"]
        == before["ledger.slice_commit_verified_count"]
    ), (
        "reconciliation must not write a ledger record -- it is read-only; "
        f"verified-slice count moved {before['ledger.slice_commit_verified_count']}"
        f" -> {after['ledger.slice_commit_verified_count']}"
    )
