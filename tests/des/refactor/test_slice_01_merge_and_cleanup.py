"""AT-5 (merge-into-clean, D4/D5) + AT-6 (mandatory cleanup, D5/D6) -- slice-01.

Layer 3 composition (in-process, L2 default). @driving_port
@contract-shape:bounded-change

RED-scaffold note: every assertion below currently fails at the FIRST call
into `RefactorDrainService.drain_one`, which raises `AssertionError` (Mandate
7) -- MISSING_FUNCTIONALITY, the correct RED classification.
"""

from __future__ import annotations

import pytest

from .composition import RefactorSwarmComposition


pytestmark = pytest.mark.acceptance


def test_merge_refuses_when_the_integration_branch_tree_is_dirty(tmp_path):
    """AT-5 / D4/D5, negative -- Given the integration branch has uncommitted
    content, When a drained item tries to merge back, Then the merge refuses
    with a named `MergeBlockedDirtyTree` outcome -- never a silent skip, never
    a corrupting 3-way attempt.

    Empirical anchor (TD-003 spike): a 2nd worktree's merge was blocked by the
    operator's OWN uncommitted WIP on the target branch, not a real conflict.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_dirty_integration_branch()
    composition.seed_pile_item(item_id="TD-001")

    result = composition.run_drain_one_item()

    assert result.merged is False, (
        "a drain must never merge into a dirty integration branch"
    )
    assert result.merge_blocked_reason == "MergeBlockedDirtyTree", (
        "a dirty integration branch must refuse with the named "
        f"MergeBlockedDirtyTree outcome; got {result.merge_blocked_reason!r}"
    )


def test_worktree_and_branch_are_removed_only_after_a_confirmed_merge(tmp_path):
    """AT-6 / D5/D6, positive -- Given a drained item's merge is CONFIRMED,
    When the drain completes, Then `git worktree remove` and `git branch -D`
    both ran -- `git worktree list` shows no dangling registration and the
    item's branch no longer exists.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    composition.seed_pile_item(item_id="TD-001")

    result = composition.run_drain_one_item()

    assert result.merged is True
    assert result.worktree_removed is True, (
        "the worktree must be removed after a CONFIRMED merge"
    )
    assert result.branch_deleted is True, (
        "the item's branch must be deleted after a CONFIRMED merge"
    )
    assert "TD-001" not in composition.worktree_list(), (
        "git worktree list must show no dangling registration after cleanup"
    )
    assert not composition.branch_exists("refactor-TD-001"), (
        "the item's branch must no longer exist after cleanup"
    )


def test_an_unmerged_branch_is_never_deleted_after_a_failed_merge(tmp_path):
    """AT-6 / D5/D6, negative -- Given a drained item's merge FAILS (dirty
    integration tree), Then cleanup does NOT run: the worktree/branch survive
    for human recovery, never silently discarded.

    Empirical anchor: the spike's own orchestration error -- an unconditional
    cleanup deleted an unmerged branch before confirming its (failed) merge,
    sending its work dangling.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_dirty_integration_branch()
    composition.seed_pile_item(item_id="TD-001")

    result = composition.run_drain_one_item()

    assert result.merged is False
    assert result.worktree_removed is False, (
        "cleanup must NEVER run after a failed (unconfirmed) merge -- an "
        "unmerged branch must never be deleted"
    )
    assert result.branch_deleted is False, (
        "an unmerged branch must survive a failed merge for human recovery"
    )
