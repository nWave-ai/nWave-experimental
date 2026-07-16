"""Charter-reconciliation ATs -- slice-01 (des-refactor-fixer-swarm).

Pins the remaining charter negative oracles
(``docs/product/expectations/des-refactor-fixer-swarm/
the-pile-drains-and-nothing-is-left-behind.md``) that were NOT yet covered by
the walking-skeleton / worktree-and-green-to-green / merge-and-cleanup /
pile-move AT files, plus the three slice-01-scoped DESIGN contract tests
(AT-2 venv isolation, AT-4 `.venv` never staged, AT-12 probe contract) the
feature-delta's Architecture & Contract Tests table declares for slice-01.

Charter oracle -> AT coverage map:

| Charter negative oracle | Covered by |
|---|---|
| false-green (item marked paid while the suite is actually red) | ``test_an_item_is_never_marked_paid_when_the_post_fix_test_run_comes_back_red`` (this file) |
| leftover-worktree | ``test_slice_01_merge_and_cleanup.py`` (AT-6) + the walking-skeleton's own branch check |
| cross-contamination (unrelated work swept into the commit) | ``test_the_merge_commit_never_touches_unrelated_operator_wip`` (this file) |
| config-ignored (wrong AI / prompt ignored / wrong cadence) | ``test_slice_01_walking_skeleton.py``'s ``capturing_agent_cmd`` + prompt-marker AT -- proves the CONFIGURED ``agent_cmd`` (not a default) is what runs, carrying the user's OWN rendered prompt |
| vacuous-green (no test coverage, must be distinguishable) | **NOT authored here** -- this is slice-04's entry-gate classifier (feature-delta Slice Plan: "characterized first or explicitly abstained ... slice-04"); the ``EntryGateVerdict``/``classify_entry_gate`` module does not exist yet (CREATE_NEW, slice-04). Authoring a behavioral AT against it now would violate atdd_pure per-slice JIT (future-slice scenarios must stay ABSENT from disk, never invented against not-yet-scaffolded code). Flagged as a genuine charter-vs-slice-plan scope tension, not silently dropped -- see this feature's DISTILL handoff report. |
| silently-dropped (an item that cannot be safely fixed must not vanish) | **Partially** covered today by ``test_slice_01_pile_move.py``'s negative AT (an item whose merge is refused stays visibly in ``techdebt.md``, never vanishes into neither pile file) -- slice-01's OWN only failure mode. The richer Mikado-escalation ``annotated "escalated"`` record is slice-04 (D9) and is likewise NOT authored here for the same per-slice-JIT reason. |

DESIGN AT-2 / AT-4 / AT-12 (slice-01-scoped per the Architecture & Contract
Tests table -- D2 per-worktree venv, D2/hygiene `.venv` never staged, and the
Earned-Trust probe contract) are authored here too since they were absent from
the prior draft.

Layer 3 composition (in-process, L2 default) throughout -- the ONE
``@walking_skeleton`` subprocess seam lives in
``test_slice_01_walking_skeleton.py``.

RED-scaffold note: every assertion below currently fails at the FIRST call
into ``RefactorDrainService.drain_one``, which raises ``AssertionError``
(Mandate 7) -- MISSING_FUNCTIONALITY, the correct RED classification.

covers: R-DES-REFACTOR-WS
"""

from __future__ import annotations

import pytest

from .composition import RefactorSwarmComposition


pytestmark = pytest.mark.acceptance


def test_an_item_is_never_marked_paid_when_the_post_fix_test_run_comes_back_red(
    tmp_path,
):
    """False-green oracle (charter negative #1) -- Given the agent's own
    change leaves the fast+impacted test subset RED after the fix, When the
    drain evaluates green-to-green, Then the item is NEVER merged and NEVER
    marked paid -- a false-green claim of success must be impossible.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    composition.seed_toy_passing_test()
    composition.seed_pile_item(item_id="TD-001")

    result = composition.run_drain_one_item(
        agent_cmd=composition.agent_cmd_that_breaks_the_test_suite()
    )

    assert result.merged is False, (
        "an item whose post-fix test run is RED must never be merged"
    )
    assert result.drained is False, (
        "an item whose post-fix test run is RED must never be reported as drained"
    )
    assert composition.pile_contains("TD-001"), (
        "an item whose fix left the suite RED must stay visible in "
        "techdebt.md -- never silently marked paid over a false green"
    )
    assert not composition.paid_contains("TD-001"), (
        "false-green claim of success: an item must NEVER be recorded in "
        "paidtechdebt.md while its test suite is actually red"
    )


def test_the_merge_commit_never_touches_unrelated_operator_wip(tmp_path):
    """Cross-contamination oracle (charter negative #3) -- Given the
    operator's own working tree has an UNRELATED untracked file at drain
    time, When the item drains and merges, Then the merge commit's diff
    never includes that unrelated file -- git worktree's clean-checkout
    isolation (D1) guarantees no unrelated work is swept into the item's own
    commit.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    composition.seed_pile_item(item_id="TD-001")
    composition.leave_unrelated_dirty_file_in_parent_tree()
    before_sha = composition.integration_branch_head_sha()

    composition.run_drain_one_item()

    after_sha = composition.integration_branch_head_sha()
    touched = composition.touched_paths_between(before_sha, after_sha)
    assert "operator_wip_unrelated.txt" not in touched, (
        "the merge commit must never sweep in unrelated operator WIP that "
        f"existed outside the item's own isolated worktree; touched={touched}"
    )


def test_each_items_worktree_is_provisioned_its_own_real_venv_directory(
    tmp_path,
):
    """AT-2 / D2, positive -- Given an item's merge is blocked (so its
    worktree survives for recovery instead of being cleaned up), Then the
    surviving worktree was provisioned its OWN real ``.venv`` directory --
    never a symlink into a shared/parent venv -- the isolation D2 exists for.

    Uses the merge-blocked path deliberately: a confirmed-merge drain removes
    its worktree (D5/D6), so the ONLY window in which a worktree's `.venv`
    is inspectable from outside is a drain whose merge never confirmed.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_dirty_integration_branch()
    composition.seed_pile_item(item_id="TD-001")

    composition.run_drain_one_item()

    worktree_path = composition.worktree_path_for_branch("refactor-TD-001")
    assert worktree_path is not None, (
        "a drain whose merge is blocked must leave its worktree registered "
        "for human recovery -- none was found"
    )
    venv_path = worktree_path / ".venv"
    assert venv_path.is_dir(), (
        f"the item's own worktree ({worktree_path}) must be provisioned a "
        f"REAL .venv directory; found nothing at {venv_path}"
    )
    assert not venv_path.is_symlink(), (
        "each item's worktree must get its OWN real .venv -- never a "
        f"symlink into a shared/parent venv; {venv_path} is a symlink"
    )


def test_the_merge_commit_never_contains_the_worktrees_venv_directory(tmp_path):
    """AT-4, positive -- Given a drain completes and merges, Then the merge
    commit's tracked paths never include the worktree's own ``.venv`` --
    the per-worktree environment is a local execution detail, never
    committed content.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    composition.seed_pile_item(item_id="TD-001")

    composition.run_drain_one_item()

    tracked = composition.integration_branch_tracked_paths()
    assert not any(path == ".venv" or path.startswith(".venv/") for path in tracked), (
        f"the merge commit must never contain the worktree's own .venv "
        f"directory; tracked paths={tracked}"
    )


def test_a_commit_that_stages_its_own_venv_directory_is_refused_before_merge(
    tmp_path,
):
    """AT-4, negative -- Given the agent's own commit accidentally stages
    ``.venv`` (a real hygiene defect), When the drain evaluates the commit
    before merge-back, Then the merge is refused with a named reason --
    never silently merged, never silently stripped without a trace.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    composition.seed_pile_item(item_id="TD-001")

    result = composition.run_drain_one_item(
        agent_cmd=composition.agent_cmd_that_stages_the_venv_directory()
    )

    assert result.merged is False, (
        "a commit that stages its own .venv must be refused before "
        "merge-back, never merged into the clean integration branch"
    )
    assert result.merge_blocked_reason is not None, (
        "the refusal must carry a NAMED reason -- never a silent skip"
    )


def test_an_unresolvable_agent_cmd_refuses_to_begin_draining_before_any_worktree_exists(
    tmp_path,
):
    """AT-12 / probe contract (principle 13) -- Given ``--agent-cmd`` names
    an executable that does not exist on PATH, When ``des refactor`` starts,
    Then it refuses BEFORE creating any worktree -- never fails midway
    through the first real item's lifecycle.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.seed_pile_item(item_id="TD-001")
    worktrees_before = composition.worktree_list()

    result = composition.run_drain_one_item(
        agent_cmd=composition.unresolvable_agent_cmd()
    )

    assert result.drained is False, (
        "an unresolvable agent_cmd must never report a drained item"
    )
    assert composition.worktree_list() == worktrees_before, (
        "a probe failure must refuse BEFORE any worktree is created -- no "
        "per-item worktree should appear when the configured agent_cmd is "
        "unresolvable"
    )
