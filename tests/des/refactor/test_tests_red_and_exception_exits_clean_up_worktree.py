"""Regression test -- bugfix-drain-cleanup-on-every-exit.

RCA: ``RefactorDrainService.drain_one`` (~line 158) and ``drain_batch``'s
inner ``_drain_concurrently`` (~line 289) leak the per-item worktree +
``refactor-<item-id>`` branch on TWO exit paths that the sibling entry-gate
fix (``bugfix-refactor-entry-gate-worktree-leak``,
``test_entry_gate_refusal_cleans_up_worktree.py``) did NOT cover:

1. **The tests-red refusal path** (``classify_green_to_green`` verdict !=
   ``SAFE``) -- ``drain_one`` returns via a bare ``self._refused(...)``
   instead of ``self._refused_after_cleanup(...)`` (the same shape
   ``_entry_gate_refusal`` already uses), so a red-tests refusal leaves a
   dangling worktree + branch. ``_drain_concurrently``'s own tests-red branch
   is asserted here too, for the SAME observable contract (``DrainResult.
   worktree_removed``/``branch_deleted`` report what actually happened).
2. **Any exception raised mid-drain** -- between worktree creation and the
   eventual cleanup/return, nothing today guards that window with a
   ``try / except BaseException: cleanup; raise``. A genuine crash (a driven
   port raising, or a future SIGINT) leaves the worktree/branch stranded on
   disk with no ``DrainResult`` at all to report it.

Explicitly OUT of scope (untouched, unweakened) -- the merge-blocked path
stays uncleaned BY DESIGN, per
``test_slice_01_merge_and_cleanup.py::test_an_unmerged_branch_is_never_deleted_after_a_failed_merge``:
an unmerged branch survives a failed merge for human recovery. Raw
SIGTERM/hard-kill and ``drain_batch``'s existing merge-blocked asymmetry vs
``drain_one`` are separate, already-filed follow-ups.

Layer 3 composition (in-process, L2 default), same driving surface every
other slice-01 AT in this directory uses:
``RefactorSwarmComposition.run_drain_one_item`` /
``run_drain_one_item_with_exploding_provision`` / ``run_drain_batch`` drive
``RefactorDrainService.drain_one`` / ``drain_batch`` directly with REAL
production adapters wired in (Pillar 3); only the non-deterministic
env-provisioning port is faked (Architecture of Reference).
"""

from __future__ import annotations

import pytest

from .composition import RefactorSwarmComposition
from .doubles import ExplodingEnvProvisionPort, FakeEnvProvisionPort, RecordingMergeLock


pytestmark = pytest.mark.acceptance

_TESTS_RED_REASON = "MergeBlockedTestsRed"


# --- drain_one: tests-red refusal ------------------------------------------


def test_a_tests_red_refusal_removes_worktree_and_branch_in_drain_one(tmp_path):
    """Given an item whose agent's own change leaves the fast+impacted test
    subset RED, When ``drain_one`` refuses the item on the tests-red path,
    Then the item's worktree AND branch are both removed -- a tests-red
    refusal must leave the repository exactly as clean as a merge-failure or
    entry-gate refusal already does.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    composition.seed_toy_passing_test()
    composition.seed_pile_item(item_id="TD-001")

    result = composition.run_drain_one_item(
        agent_cmd=composition.agent_cmd_that_breaks_the_test_suite_after_passing_entry_gate()
    )

    assert result.merged is False
    assert result.merge_blocked_reason == _TESTS_RED_REASON
    assert result.worktree_removed is True, (
        "a tests-red refusal must remove the item's worktree, exactly like "
        "a merge-failure or entry-gate refusal does"
    )
    assert result.branch_deleted is True, (
        "a tests-red refusal must delete the item's branch, exactly like "
        "a merge-failure or entry-gate refusal does"
    )
    assert "TD-001" not in composition.worktree_list(), (
        "git worktree list must show no dangling registration after a "
        "tests-red refusal -- a stray worktree was left behind"
    )
    assert not composition.branch_exists("refactor-TD-001"), (
        "the item's refactor-TD-001 branch must no longer exist after a "
        "tests-red refusal -- a stray branch was left behind"
    )


# --- drain_one: mid-drain exception -----------------------------------------


def test_b_a_mid_drain_exception_never_strands_worktree_or_branch_in_drain_one(
    tmp_path,
):
    """Given a driven port (env-provisioning) raises a genuine exception
    AFTER the item's worktree already exists, When ``drain_one`` propagates
    that exception, Then the worktree AND branch are still removed on disk --
    the exception is not swallowed (it re-raises to the caller), but it must
    not strand the git state behind it either.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    composition.seed_toy_passing_test()
    composition.seed_pile_item(item_id="TD-001")

    with pytest.raises(RuntimeError):
        composition.run_drain_one_item_with_exploding_provision()

    assert "TD-001" not in composition.worktree_list(), (
        "git worktree list must show no dangling registration after a "
        "mid-drain crash -- a stray worktree was left behind"
    )
    assert not composition.branch_exists("refactor-TD-001"), (
        "the item's refactor-TD-001 branch must no longer exist after a "
        "mid-drain crash -- a stray branch was left behind"
    )


# --- drain_batch / _drain_concurrently: tests-red refusal -------------------


def test_c_a_tests_red_refusal_removes_worktree_and_branch_in_drain_batch(tmp_path):
    """Given a single-item batch whose agent's own change leaves the
    fast+impacted test subset RED, When ``drain_batch``'s
    ``_drain_concurrently`` refuses the item on the tests-red path, Then the
    item's own ``DrainResult`` reports the worktree AND branch as removed --
    the SAME observable contract ``drain_one``'s tests-red refusal owes
    (Mandate 8: ``DrainResult.worktree_removed``/``branch_deleted`` are the
    port-exposed universe a caller polls to decide whether cleanup ran), and
    the git-observable state confirms it.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    composition.seed_toy_passing_test()
    composition.seed_pile_item(item_id="TD-001")

    batch_result = composition.run_drain_batch(
        merge_lock=RecordingMergeLock(),
        env_provision=FakeEnvProvisionPort(),
        item_count=1,
        max_parallel=1,
        agent_cmd=composition.agent_cmd_that_breaks_the_test_suite_after_passing_entry_gate(),
    )

    (result,) = batch_result.results
    assert result.merged is False
    assert result.merge_blocked_reason == _TESTS_RED_REASON
    assert result.worktree_removed is True, (
        "a tests-red refusal inside drain_batch must report the item's "
        "worktree as removed, exactly like drain_one's tests-red refusal"
    )
    assert result.branch_deleted is True, (
        "a tests-red refusal inside drain_batch must report the item's "
        "branch as deleted, exactly like drain_one's tests-red refusal"
    )
    assert "TD-001" not in composition.worktree_list(), (
        "git worktree list must show no dangling registration after a "
        "batch tests-red refusal -- a stray worktree was left behind"
    )
    assert not composition.branch_exists("refactor-TD-001"), (
        "the item's refactor-TD-001 branch must no longer exist after a "
        "batch tests-red refusal -- a stray branch was left behind"
    )


# --- drain_batch / _drain_concurrently: mid-drain exception -----------------


def test_d_a_mid_drain_exception_never_strands_worktree_or_branch_in_drain_batch(
    tmp_path,
):
    """Given a single-item batch whose env-provisioning port raises a
    genuine exception AFTER the item's worktree already exists, When
    ``drain_batch`` propagates that exception (via the worker future), Then
    the worktree AND branch are still removed on disk -- a crash inside one
    concurrent lane must not strand that lane's git state.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    composition.seed_toy_passing_test()
    composition.seed_pile_item(item_id="TD-001")

    with pytest.raises(RuntimeError):
        composition.run_drain_batch(
            merge_lock=RecordingMergeLock(),
            env_provision=ExplodingEnvProvisionPort(),
            item_count=1,
            max_parallel=1,
        )

    assert "TD-001" not in composition.worktree_list(), (
        "git worktree list must show no dangling registration after a "
        "batch mid-drain crash -- a stray worktree was left behind"
    )
    assert not composition.branch_exists("refactor-TD-001"), (
        "the item's refactor-TD-001 branch must no longer exist after a "
        "batch mid-drain crash -- a stray branch was left behind"
    )
