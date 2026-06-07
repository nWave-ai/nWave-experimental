"""Step definitions for slice-02 -- DISTILL dispatch marker enforcement +
DELIVER-exit symmetry.

slice-02 of oss-hook-side-phase-injection (the DISTILL-wave hook keystone, D1).

Step bodies are delegate-only (Mandate-12 criterion 3): each is a single typed
lookup into the ``slice02_domain_types`` phrase tables plus one composition
call. All gate logic lives in the production PreToolUse / SubagentStop handlers;
the composition roots only wire the real hook subprocesses and read back the
observable ledger substrate.

S1 (step-text uniqueness) note: every literal step string in this module is
distinct from the slice-01 ``test_g_distill_exit_gate.py`` literals in the same
feature directory -- the AT-3 ``When`` / exit-code phrases are deliberately
worded ("the crafter return", "the DELIVER-exit hook exits") so no
``(step_type, literal)`` key is double-registered across the two step files.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .slice02_composition import (
    DistillDispatchGateComposition,
    DistillDispatchOutcome,
    GCommitExitGateComposition,
    GCommitExitOutcome,
)
from .slice02_domain_types import (
    DEFECTIVE_DISPATCH_SHAPE_BY_PHRASE,
    DISTILL_DISPATCH_BLOCK_EVENT_BY_PHRASE,
    DispatchVerdict,
    DistillDispatchShape,
    GCommitOutcome,
)


scenarios("../distill-dispatch-and-deliver-exit-symmetry.feature")


# --- fixtures -----------------------------------------------------------------


@pytest.fixture
def distill_dispatch(tmp_path: Path) -> DistillDispatchGateComposition:
    return DistillDispatchGateComposition(tmp_path)


@pytest.fixture
def g_commit_exit(tmp_path: Path) -> GCommitExitGateComposition:
    comp = GCommitExitGateComposition(tmp_path)
    comp.init_repo()
    return comp


@pytest.fixture
def dispatch_holder() -> dict[str, DistillDispatchOutcome]:
    return {}


@pytest.fixture
def g_commit_holder() -> dict[str, GCommitExitOutcome]:
    return {}


# --- AT-1 / AT-2: G-DISTILL-PRE marker enforcement (PreToolUse) ---------------


@given("a DISTILL acceptance-designer dispatch carrying a complete marker set")
def _given_complete_dispatch(distill_dispatch: DistillDispatchGateComposition) -> None:
    distill_dispatch.use_dispatch(DistillDispatchShape.COMPLETE)


@given(parsers.parse("a DISTILL acceptance-designer dispatch that {defect}"))
def _given_defective_dispatch(
    distill_dispatch: DistillDispatchGateComposition, defect: str
) -> None:
    distill_dispatch.use_dispatch(DEFECTIVE_DISPATCH_SHAPE_BY_PHRASE[defect])


@when("the PreToolUse hook validates the dispatch")
def _when_pre_tool_use_runs(
    distill_dispatch: DistillDispatchGateComposition,
    dispatch_holder: dict[str, DistillDispatchOutcome],
) -> None:
    dispatch_holder["result"] = distill_dispatch.run_pre_tool_use_hook()


@then("the DISTILL dispatch gate allows the dispatch")
def _then_dispatch_allowed(
    dispatch_holder: dict[str, DistillDispatchOutcome],
) -> None:
    assert dispatch_holder["result"].verdict == DispatchVerdict.ALLOWED


@then(parsers.parse("the DISTILL dispatch gate reports {block_phrase}"))
def _then_dispatch_blocked_with_event(
    dispatch_holder: dict[str, DistillDispatchOutcome], block_phrase: str
) -> None:
    expected_event = DISTILL_DISPATCH_BLOCK_EVENT_BY_PHRASE[block_phrase]
    result = dispatch_holder["result"]
    assert result.verdict == DispatchVerdict.BLOCKED
    assert result.block_event == expected_event


@then("the hook allows with exit code zero")
def _then_dispatch_exit_zero(
    dispatch_holder: dict[str, DistillDispatchOutcome],
) -> None:
    assert dispatch_holder["result"].exit_code == 0


@then("the hook blocks with exit code two")
def _then_dispatch_exit_two(
    dispatch_holder: dict[str, DistillDispatchOutcome],
) -> None:
    assert dispatch_holder["result"].exit_code == 2


# --- AT-3: G-DELIVER-EXIT symmetry (SubagentStop G_COMMIT) --------------------


@given("an atdd_pure crafter has committed a complete slice commit")
def _given_complete_slice_commit(g_commit_exit: GCommitExitGateComposition) -> None:
    g_commit_exit.make_complete_slice_commit()


@given("the crafter returns from the DELIVER commit phase")
def _given_g_commit_return(g_commit_exit: GCommitExitGateComposition) -> None:
    g_commit_exit.write_g_commit_return_transcript()


@when("the SubagentStop hook processes the crafter return")
def _when_subagent_stop_runs(
    g_commit_exit: GCommitExitGateComposition,
    g_commit_holder: dict[str, GCommitExitOutcome],
) -> None:
    g_commit_holder["result"] = g_commit_exit.run_subagent_stop_hook()


@then("the DELIVER-exit gate records a verified slice commit")
def _then_slice_commit_verified(
    g_commit_holder: dict[str, GCommitExitOutcome],
) -> None:
    result = g_commit_holder["result"]
    assert result.outcome == GCommitOutcome.VERIFIED
    assert result.slice_commit_verified_emitted is True


@then("the DELIVER-exit gate writes a DELIVER phase-completed record for that slice")
def _then_phase_completed_g_commit(
    g_commit_holder: dict[str, GCommitExitOutcome],
) -> None:
    result = g_commit_holder["result"]
    assert result.phase_completed_g_commit_emitted is True
    assert result.phase_completed_g_commit_slice_id == "slice-02"


@then("the DELIVER-exit hook exits with code zero")
def _then_g_commit_exit_zero(
    g_commit_holder: dict[str, GCommitExitOutcome],
) -> None:
    assert g_commit_holder["result"].exit_code == 0
