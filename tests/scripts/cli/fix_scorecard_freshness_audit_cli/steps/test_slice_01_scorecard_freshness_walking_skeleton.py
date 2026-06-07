"""Step definitions -- slice-01: scorecard-freshness-audit walking skeleton.

F-CROSS-TREE-SCORECARD-FRESHNESS-AUDIT-CLI slice-01. Layer 3 (subprocess / FS
acceptance): the ``check_scorecard_freshness`` CLI is the driving port; the
driven ports are the real filesystem (tmp_path) and the real git subprocess.
Example-based (Mandate 11) -- the walking-skeleton ATs cover ONE happy path,
ONE sad path, and ONE read-only preservation invariant.

Step bodies delegate to ``ScorecardFreshnessComposition`` -- a typed lookup
plus a composition call, no inline logic (Mandate-12 criterion 3). The
preservation AT asserts the scorecard file is byte-identical before/after via
``assert_state_delta`` over a port-exposed universe (Mandate 8).

This slice is RED-for-the-right-reason against the slice-01 production
``check_scorecard_freshness`` scaffold. The DELIVER crafter authors the RED
scaffold first (Mandate 7) -- entry point raises ``AssertionError`` -- then
GREEN steps implement the actual freshness-detection logic until the three
slice-01 ATs go GREEN. Until the scaffold lands, the subprocess invocations
exit non-zero with ``ModuleNotFoundError``, which still surfaces as a
fail-for-the-right-reason AssertionError on the @then verdict assertion.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .composition import ScorecardFreshnessComposition
from .domain_types import (
    EXIT_CODE_BY_VERDICT,
    FreshnessCliResult,
    ScorecardFreshnessVerdict,
)


scenarios("../slice-01-scorecard-freshness-walking-skeleton.feature")


# --- Fixtures --------------------------------------------------------------


@pytest.fixture
def composition(tmp_path: Path) -> ScorecardFreshnessComposition:
    """Production-wired composition root over a tmp_path scorecard project."""
    return ScorecardFreshnessComposition(project_root=tmp_path / "project")


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for the CLI result + scenario-derived state across steps."""
    return {}


# --- Background -------------------------------------------------------------


@given("a project root with a backing git repository")
def given_project_with_git(composition: ScorecardFreshnessComposition) -> None:
    composition.init_project_with_backing_git()


# --- Given ------------------------------------------------------------------


@given("the producer wave has recently landed commits for every cited F-id")
def given_all_fresh_commits(composition: ScorecardFreshnessComposition) -> None:
    composition.write_fresh_commit_for_fid()


@given(
    "the acceptance designer has authored a scorecard whose every cell cites a recently-landed F-id"
)
def given_scorecard_all_fresh_cells(
    composition: ScorecardFreshnessComposition,
) -> None:
    composition.write_scorecard_with_all_fresh_cells()


@given(
    "the producer wave has recently landed commits for one cited F-id but not another"
)
def given_mixed_fresh_and_stale_commits(
    composition: ScorecardFreshnessComposition,
) -> None:
    composition.write_fresh_commit_for_fid()
    composition.write_stale_commit_for_fid()


@given(
    "the acceptance designer has authored a scorecard with one fresh cell and one stale cell"
)
def given_scorecard_one_stale_cell(
    composition: ScorecardFreshnessComposition,
) -> None:
    composition.write_scorecard_with_one_stale_cell()


# --- When -------------------------------------------------------------------


@when("the reviewer runs the freshness audit on the scorecard")
def when_run_freshness_audit(
    composition: ScorecardFreshnessComposition, result_box: dict[str, object]
) -> None:
    before = composition.capture_universe()
    result_box["result"] = composition.run_check_scorecard_freshness()
    after = composition.capture_universe()
    # The freshness audit is a pure-function READ over the scorecard: no
    # file in the universe transitions, no bytes mutate. The CLI may emit
    # verdict bytes to stdout/stderr but MUST NOT mutate the scorecard
    # file. State-delta universe is port-exposed names only (Mandate 8).
    assert_state_delta(
        before=before,
        after=after,
        universe={
            "scorecard.present",
            "scorecard.bytes",
        },
        expected={
            "scorecard.present": unchanged(),
            "scorecard.bytes": unchanged(),
        },
    )


# --- Then -------------------------------------------------------------------


@then("the freshness audit reports the scorecard as freshly verified")
def then_audit_reports_pass(
    composition: ScorecardFreshnessComposition, result_box: dict[str, object]
) -> None:
    result: FreshnessCliResult = result_box["result"]  # type: ignore[assignment]
    expected_exit = EXIT_CODE_BY_VERDICT[ScorecardFreshnessVerdict.PASS]
    assert result.exit_code == expected_exit, (
        f"expected exit {expected_exit} (PASS); got {result.exit_code}\n"
        f"-- stdout: {result.stdout!r}\n"
        f"-- stderr: {result.stderr!r}"
    )
    assert composition.stdout_carries_verdict(result, ScorecardFreshnessVerdict.PASS), (
        f"stdout token missing verdict=PASS\n--\n{result.stdout}"
    )


@then("the freshness audit reports the scorecard as failing freshness")
def then_audit_reports_fail(
    composition: ScorecardFreshnessComposition, result_box: dict[str, object]
) -> None:
    result: FreshnessCliResult = result_box["result"]  # type: ignore[assignment]
    expected_exit = EXIT_CODE_BY_VERDICT[ScorecardFreshnessVerdict.FAIL]
    assert result.exit_code == expected_exit, (
        f"expected exit {expected_exit} (FAIL); got {result.exit_code}\n"
        f"-- stdout: {result.stdout!r}\n"
        f"-- stderr: {result.stderr!r}"
    )
    assert composition.stdout_carries_verdict(result, ScorecardFreshnessVerdict.FAIL), (
        f"stdout token missing verdict=FAIL\n--\n{result.stdout}"
    )


@then("the freshness audit names the stale cell so the reviewer can re-baseline it")
def then_audit_names_stale_cell(
    composition: ScorecardFreshnessComposition, result_box: dict[str, object]
) -> None:
    result: FreshnessCliResult = result_box["result"]  # type: ignore[assignment]
    assert composition.stdout_names_stale_fid(result), (
        "stale F-id not surfaced in stdout/stderr -- the consumer cannot "
        "tell WHICH cell is stale; the verdict is FAIL but the cause-of-"
        "failure is hidden\n"
        f"-- stdout: {result.stdout!r}\n"
        f"-- stderr: {result.stderr!r}"
    )


@then("the scorecard file content is unchanged after the audit runs")
def then_scorecard_unchanged(
    composition: ScorecardFreshnessComposition, result_box: dict[str, object]
) -> None:
    # The state-delta assertion in the @when step enforces byte-equality.
    # But state-delta passes VACUOUSLY when the CLI fails to even start
    # (ModuleNotFoundError → exit 1 → CLI does nothing → universe trivially
    # unchanged). Per the "No Fixture Theater" agent rule, this @then must
    # ALSO assert the CLI invocation was MEANINGFUL: the CLI actually ran
    # to completion and emitted the PASS verdict, so the preservation
    # contract is proven on a real read-path, not on a non-execution. If
    # the crafter's eventual GREEN implementation accidentally writes to
    # the scorecard, the @when state-delta assertion fires; if the CLI
    # silently no-ops, this exit-code precondition fires.
    result: FreshnessCliResult = result_box["result"]  # type: ignore[assignment]
    expected_exit = EXIT_CODE_BY_VERDICT[ScorecardFreshnessVerdict.PASS]
    assert result.exit_code == expected_exit, (
        f"preservation AT vacuously passes -- the CLI did not run a full "
        f"freshness audit (expected exit {expected_exit} PASS; got "
        f"{result.exit_code}). State-delta byte-equality alone proves the "
        f"file unchanged ONLY when the CLI actually ran. The crafter must "
        f"ship the GREEN implementation before this AT is non-vacuous.\n"
        f"-- stdout: {result.stdout!r}\n"
        f"-- stderr: {result.stderr!r}"
    )
