# @feature-des-refactor-fixer-swarm
"""Regression AT -- bugfix-refactor-entry-gate-missing-from-drain-batch.

Defect: `RefactorDrainService.drain_one`'s D9 entry-gate refusal
(`_entry_gate_refusal`) is wired in right after `_dispatch_agent` -- but
`_drain_concurrently` (the per-item worker `drain_batch` submits to its
thread pool) never calls it at all. The result: an item whose agent emits
NO recognized entry-gate verdict token (or escalates to Mikado) is
correctly refused at `--max-parallel 1` (`drain_one`) yet merges SILENTLY
at `--max-parallel 2+` (`drain_batch` -> `_drain_concurrently`) -- exactly
the "silently 'verified' against a vacuous/unclassified green" failure mode
slice-04's entry gate exists to close (see test_slice_04_entry_gate.py),
reopened for the batch path.

Layer 3 composition, matching test_slice_02_concurrent_drain.py's own
driving surface (`RefactorSwarmComposition.run_drain_batch`).
"""

from __future__ import annotations

import pytest

from .composition import RefactorSwarmComposition
from .doubles import FakeEnvProvisionPort, RecordingMergeLock


pytestmark = pytest.mark.acceptance

_ENTRY_GATE_VERDICT_MISSING = "EntryGateVerdictMissing"


def test_unclassified_item_batch_drain_refuses_merge_matching_drain_one(tmp_path):
    """AT-7 batch-path parity -- Given a single pile item whose agent emits
    no recognized entry-gate verdict, When it drains via `drain_batch` at
    `--max-parallel` 2 (two lanes requested even though only one item is
    seeded -- the concurrent code path `_drain_concurrently` is what must be
    exercised), Then it must be refused with `EntryGateVerdictMissing` and
    NEVER merged or moved to paidtechdebt.md -- the SAME outcome
    `drain_one` (`--max-parallel` 1) already produces for the identical
    Given (test_slice_04_entry_gate.py).
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.seed_disjoint_pile_items(("TD-001",))
    env_provision = FakeEnvProvisionPort()
    merge_lock = RecordingMergeLock()

    batch = composition.run_drain_batch(
        merge_lock=merge_lock,
        env_provision=env_provision,
        item_count=1,
        max_parallel=2,
        agent_cmd=composition.agent_cmd_emitting_no_recognized_verdict(),
    )

    results_by_id = {result.item_id: result for result in batch.results}
    result = results_by_id["TD-001"]
    assert result.merged is False, (
        "an item whose agent output carries no recognized entry-gate "
        "verdict token must NEVER be merged via the BATCH drain path either "
        "-- even when its tests stay green"
    )
    assert result.merge_blocked_reason == _ENTRY_GATE_VERDICT_MISSING, (
        "a missing entry-gate verdict must refuse with the NAMED "
        f"EntryGateVerdictMissing outcome; got {result.merge_blocked_reason!r}"
    )
    assert composition.pile_contains("TD-001"), (
        "an item refused for a missing entry-gate verdict must stay "
        "visible in techdebt.md, never silently vanish"
    )
    assert not composition.paid_contains("TD-001"), (
        "an item refused for a missing entry-gate verdict must NEVER be "
        "recorded in paidtechdebt.md via the batch path -- never a silent merge"
    )
    assert not composition.branch_exists("refactor-TD-001"), (
        "an entry-gate refusal on the batch path must clean up the "
        "worktree/branch it was handed, same cleanup guarantee as "
        "drain_one's _refused_after_cleanup"
    )
