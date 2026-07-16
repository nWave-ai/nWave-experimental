"""AT-1 (worktree-from-tip, D1) + AT-3/AT-10 (green-to-green, D3) -- slice-01.

Layer 3 composition (in-process, L2 default) -- drives
`RefactorDrainService.drain_one` directly with the real production adapters
(Pillar 3), never a re-forked interpreter (subprocess-e2e is reserved for the
one `@walking_skeleton` in test_slice_01_walking_skeleton.py).

@driving_port @contract-shape:bounded-change

RED-scaffold note: every assertion below currently fails at the FIRST call
into `RefactorDrainService.drain_one`, which raises `AssertionError` (Mandate
7) -- MISSING_FUNCTIONALITY, the correct RED classification.
"""

from __future__ import annotations

import pytest

from .composition import RefactorSwarmComposition


pytestmark = pytest.mark.acceptance


def test_worktree_is_cut_from_the_current_head_never_a_stale_ancestor(tmp_path):
    """AT-1 / D1 -- Given HEAD advances between session start and drain time,
    When the item drains, Then the created worktree's HEAD sha equals the
    CURRENT parent-repo HEAD sha at drain time, never a stale ancestor.

    Empirical anchor: the Agent-tool's own `isolation: worktree` mode was
    measured 1664 commits behind HEAD (`feedback_isolation_worktree_stale_
    base`) -- this AT pins the fix (`git worktree add -b <branch> <path>
    HEAD`, cut at the INSTANT the item starts draining).
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.seed_pile_item(item_id="TD-001")
    # The repo advances AFTER the pile item was seeded -- simulates the gap
    # between "session start" and the instant this item actually drains.
    current_head = composition.advance_head_with_unrelated_commit()

    result = composition.run_drain_one_item()

    assert result.worktree_head_sha_at_creation == current_head, (
        "the worktree must be cut from the CURRENT branch tip at drain time, "
        f"never a stale ancestor; got "
        f"{result.worktree_head_sha_at_creation!r}, expected {current_head!r}"
    )


def test_a_second_items_worktree_never_reuses_a_stale_head_from_the_first_drain(
    tmp_path,
):
    """AT-1 / D1, negative -- Given item A drains, then HEAD advances again,
    When item B drains, Then item B's worktree reflects the SECOND advance,
    never a cached HEAD from item A's own drain.

    Negative AT (GS-8): a harness that memoises "the" HEAD sha once (at
    session/process start) instead of re-reading it per item would pass a
    single-item test while still reproducing the stale-ancestor bug on the
    SECOND item -- this pins that no such caching happens.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.seed_pile_item(item_id="TD-001")
    composition.advance_head_with_unrelated_commit()
    composition.run_drain_one_item()

    composition.seed_pile_item(item_id="TD-002")
    second_head = composition.advance_head_with_unrelated_commit()
    result = composition.run_drain_one_item()

    assert result.worktree_head_sha_at_creation == second_head, (
        "item B's worktree must never reuse a HEAD sha captured for a prior "
        f"item; got {result.worktree_head_sha_at_creation!r}, expected "
        f"{second_head!r}"
    )


def test_green_to_green_reads_the_test_result_envelope_never_scraped_stdout(
    tmp_path,
):
    """AT-3 / D3, positive -- Given a drain completes, When the green-to-green
    comparison runs, Then its verdict is sourced from the `nwave.test_result.v1`
    envelope fields, never scraped from the runner's rich-reporter stdout.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.seed_pile_item(item_id="TD-001")

    result = composition.run_drain_one_item()

    assert result.test_result_source == "envelope", (
        "the green-to-green comparison must read the nwave.test_result.v1 "
        f"envelope, never parsed stdout; got {result.test_result_source!r}"
    )


def test_green_to_green_never_invokes_the_full_suite_as_the_per_item_gate(
    tmp_path,
):
    """AT-10 / D3, negative -- Given a drain completes, Then the green-to-green
    comparison's scope is bounded to fast+impacted tests, never the full suite.

    Design doc §7/§9: full-suite x N concurrent agents serialises
    catastrophically on the shared box; full suite is a PERIODIC backstop,
    never the per-item gate.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.seed_pile_item(item_id="TD-001")

    result = composition.run_drain_one_item()

    assert result.test_target_scope == "fast+impacted", (
        "the per-item green-to-green gate must never run the full suite; "
        f"got test_target_scope={result.test_target_scope!r}"
    )
