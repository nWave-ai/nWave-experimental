# @feature-des-refactor-fixer-swarm
# @slice-01
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


def test_a_successful_drain_leaves_no_integration_branch_and_lands_the_fix(tmp_path):
    """Charter oracle 'nothing is left behind' + 'git log shows the fix'
    (docs/product/expectations/des-refactor-fixer-swarm/
    the-pile-drains-and-nothing-is-left-behind.md, lines 32 + 39-46) --
    Given a drained item whose fix is real and keeps the suite green, When the
    drain completes, Then the fix commit is reachable from the operator's OWN
    branch (so a maintainer's `git log` shows it) AND no stray branch survives:
    neither the per-item `refactor-<id>` NOR the `refactor-integration` branch,
    which did NOT exist before the run and must be gone after -- and no
    worktree is left registered. The repository looks like nobody was ever
    there.

    The integration branch is NOT pre-created here (unlike the sibling ATs):
    the service creates it on the fly, exactly as a real `des refactor` run
    does -- so a branch left behind is a branch the RUN created, the charter's
    'no extra branch beyond what existed before' condition.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.seed_toy_passing_test()
    composition.seed_pile_item(item_id="TD-001")
    head_before = composition.repo_head_sha()

    result = composition.run_drain_one_item(
        agent_cmd=composition.agent_cmd_that_makes_a_benign_real_change()
    )

    assert result.merged is True
    assert composition.repo_head_sha() != head_before, (
        "the drained fix must land on the operator's own branch so a "
        "maintainer's `git log` shows it -- the operator HEAD did not advance, "
        "meaning the fix is stranded on a branch the maintainer never sees"
    )
    assert not composition.branch_exists("refactor-TD-001"), (
        "the per-item branch must not survive a successful drain"
    )
    assert not composition.branch_exists("refactor-integration"), (
        "the integration branch did not exist before the run and must be gone "
        "after -- no stray branch left behind (charter: nothing is left behind)"
    )
    assert "refactor-" not in composition.worktree_list(), (
        "no per-item worktree may be left registered after a successful drain"
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
