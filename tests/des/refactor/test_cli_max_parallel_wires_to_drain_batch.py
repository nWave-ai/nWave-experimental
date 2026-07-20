# @feature-des-refactor-fixer-swarm
# @bugfix-refactor-cli-max-parallel-unwired
"""Regression AT -- `des refactor --max-parallel N` must actually invoke
``RefactorDrainService.drain_batch``, not silently stay on the single-item
``drain_one`` path.

RCA (bugfix-refactor-cli-max-parallel-unwired dispatch): `_parse_args` in
`src/des/cli/refactor.py` parses `--max-parallel`/`--driver` into `args`, but
`main()` unconditionally calls `service.drain_one(...)` regardless of their
value. Confirmed via feature-end EXAMINE (nw-user-examiner, black-box CLI
run): `des refactor --pile techdebt.md --agent-cmd true --max-parallel 2`
against a 2-item disjoint pile only ever created ONE worktree -- the second
item was never attempted. `--max-parallel N` for any N>1 is silently a no-op
today.

This is a bugfix-lane regression test (ADR-025 SLIM-crafter discipline: no
feature-delta.md for this bugfix) -- Layer 2 in-process (`composition.
call_refactor_main_in_process_with_max_parallel`) drives the REAL installed
CLI entry, never a fixture standing in for it (Fixture Theater would hide the
exact defect this test exists to catch).
"""

from __future__ import annotations

import pytest

from .composition import RefactorSwarmComposition


pytestmark = pytest.mark.acceptance


def test_cli_max_parallel_drains_multiple_disjoint_items_concurrently(tmp_path):
    """Given a 2-item disjoint pile, When `des refactor` runs with
    `--max-parallel 2`, Then BOTH items are drained -- not just the first.

    Before the fix: `main()` ignores `args.max_parallel` and always calls
    `drain_one`, so only TD-001 drains and TD-002 is left untouched in
    techdebt.md -- the exact silent no-op the RCA observed black-box.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    item_ids = ("TD-001", "TD-002")
    composition.seed_disjoint_pile_items(item_ids)

    exit_code = composition.call_refactor_main_in_process_with_max_parallel(
        max_parallel=2,
        agent_cmd=composition.agent_cmd_that_fixes_the_items_own_file(),
    )

    assert exit_code == 0, (
        "des refactor --max-parallel 2 over a 2-item disjoint pile should "
        f"exit 0; got {exit_code}"
    )
    for item_id in item_ids:
        assert not composition.pile_contains(item_id), (
            f"{item_id} must be drained (removed from techdebt.md) under "
            "--max-parallel 2 -- it must not be silently left behind"
        )
        assert composition.paid_contains(item_id), (
            f"{item_id} must be recorded in paidtechdebt.md once drained "
            "under --max-parallel 2"
        )
    tracked = composition.integration_branch_tracked_paths()
    for item_id in item_ids:
        assert f"fixed-{item_id}.txt" in tracked, (
            f"{item_id}'s own commit is missing from the integration "
            f"branch's final tree under --max-parallel 2 -- got {tracked!r}"
        )


def test_cli_max_parallel_default_still_calls_drain_one_for_a_single_item(
    tmp_path,
):
    """Given the default `--max-parallel 1` (unset), When `des refactor`
    runs, Then the existing single-item `drain_one` path behaves exactly as
    before the fix -- this pins the explicit non-regression requirement from
    the dispatch (do not change the max_parallel=1/default path)."""
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.seed_pile_item(item_id="TD-001")

    exit_code = composition.call_refactor_main_in_process(
        agent_cmd="sh -c \"printf 'REFACTOR_SAFE\\n'\""
    )

    assert exit_code == 0
    assert not composition.pile_contains("TD-001")
    assert composition.paid_contains("TD-001")
