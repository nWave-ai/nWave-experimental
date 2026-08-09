# @feature-des-refactor-fixer-swarm
# @slice-02
"""Concurrent-drain AT set -- des-refactor-fixer-swarm slice-02.

@driving_port @contract-shape:bounded-change (feature-delta Slice Plan).
Value statement: "Multiple DISJOINT pile items drain CONCURRENTLY (separate
worktrees, separate venvs) without cross-contaminating each other's
environment or corrupting a shared merge target -- the green-to-green
verification + merge-back serialize behind one lock, the LLM reasoning
lanes do not." Design doc §9.

No new walking-skeleton here -- the feature's single ``@walking_skeleton``
lives in slice-01 (test_slice_01_walking_skeleton.py); every AT below drives
``RefactorDrainService.drain_batch`` in-process (Layer 3 composition, the L2
in-process default). ``@real-io`` (Mandate 14 OR-reduction): the composition
wires a REAL ``GitWorktreeAdapter``/``ShellAgentInvocationAdapter`` --
``FakeEnvProvisionPort``/``RecordingMergeLock`` are the ONLY fakes (driven
external/non-deterministic ports per the Architecture of Reference), so PBT
is precluded and every scenario below is example-based (Mandate 9/11).

RED-scaffold note: ``RefactorDrainService.drain_batch`` raises
``AssertionError("RED scaffold: ...")`` the instant it is called (Mandate 7)
-- every AT in this file therefore fails at that first productive call,
MISSING_FUNCTIONALITY, before any of its own domain assertions run.

Requirement coverage markers (`# covers: Rn`) sit INSIDE each test body below
-- a module-level docstring marker is a known silent-drop the spec-coverage
scanner does not scan (`nw-distill` Gotchas).

AT-to-test mapping (peer-review revision) -- feature-delta's DESIGN wave
declares a 12-item contract-test table (AT-1..AT-12), authored against the
SINGLE-item lifecycle (D1-D10). This file introduces ZERO new AT-N numbers:
AT-1/3/4/5/10/12 are single-item invariants with no concurrency dimension --
fully owned and already shipped by slice-01 (see
``test_slice_01_worktree_and_green_to_green.py``,
``test_slice_01_merge_and_cleanup.py``,
``test_slice_01_safety_and_isolation.py``); AT-7/AT-8 (entry gate / Mikado)
belong to slice-04; AT-9 (paradigm refusal) belongs to slice-05; AT-11
(DES-MODE dispatch) belongs to slice-03 -- none of those five are re-tested
here (per-slice JIT, atdd_pure). Exactly TWO of the 12 rows have a genuine
concurrency dimension the single-item slice-01 suite could not close alone,
and THIS file is what closes them:

* **AT-2** (D2, per-worktree venv isolation) -- its own DESIGN wording reads
  "Given TWO items draining concurrently, each worktree has its own
  ``.venv``" (feature-delta Architecture & Contract Tests table). slice-01's
  ``test_each_items_worktree_is_provisioned_its_own_real_venv_directory``
  only ever drains ONE item -- it proves the venv is real, never that N
  concurrent venvs stay isolated from each other.
  ``test_disjoint_items_drain_concurrently_each_in_its_own_worktree_and_venv``
  below closes that literal clause (asserts ``len(set(provisioned)) ==
  item_count`` -- every concurrent item's venv path is DISTINCT).
* **AT-6** (D5, cleanup only-after-confirmed-merge) -- slice-01 proves the
  single-item ordering invariant. A shared-repo cleanup race across N
  SIMULTANEOUS items (two lanes racing ``git worktree remove``/
  ``git branch -D`` against the same repo) is a failure mode single-item
  testing cannot surface at all;
  ``test_disjoint_items_drain_concurrently_each_in_its_own_worktree_and_venv``'s
  ``assert_state_delta`` (``git.worktree_list``/``git.head_sha`` unchanged
  once the WHOLE batch settles) re-confirms the SAME invariant holds under
  concurrency.

The remaining THREE tests in this file realize claims that have NO AT-1..12
counterpart at all -- concurrency-under-load was never in the original
12-item table's scope (it predates slice-02's own D7/§9 concern). They are
tracked instead as R2/R3/R4/R5 in
``docs/feature/des-refactor-fixer-swarm/distill/requirement-checklist.md``
(R1 is the AT-2/AT-6 closure above):

| Test (this file) | Requirement | AT-1..12 counterpart |
|---|---|---|
| ``test_disjoint_items_drain_concurrently_each_in_its_own_worktree_and_venv[2,3]`` | R1 | AT-2 + AT-6 (concurrency closure, above) |
| ``test_agent_reasoning_lanes_run_concurrently_while_the_shared_box_serializes[2,3]`` | R2 | none -- N-party barrier proof is new to slice-02 |
| ``test_green_to_green_and_merge_back_never_overlap_across_concurrent_items`` | R3 | none -- mutual-exclusion witness log is new to slice-02 |
| ``test_a_failing_items_broken_change_never_leaks_into_a_sibling_items_worktree`` | R4 | none -- cross-item isolation half of the false-green oracle (slice-01's ``test_an_item_is_never_marked_paid_when_the_post_fix_test_run_comes_back_red`` covers the single-item half only) |
| ``test_two_concurrent_merges_never_drop_either_items_commit_from_the_integration_branch`` | R5 | none -- lost-update race is new to slice-02 |

``test_default_batch_composition_wires_the_real_agent_invocation_adapter_with_no_barrier``
carries no R-number -- it is a composition-root wiring regression (shard-3
CI fix, 2026-08-09), not a domain-level AT/requirement.
"""

from __future__ import annotations

import pytest

from tests.common.state_delta import assert_state_delta, unchanged

from .composition import RefactorSwarmComposition
from .doubles import FakeEnvProvisionPort, RecordingMergeLock


pytestmark = pytest.mark.acceptance


@pytest.mark.parametrize("item_count", [2, 3])
def test_disjoint_items_drain_concurrently_each_in_its_own_worktree_and_venv(
    tmp_path, item_count
):
    """Given N disjoint pile items, When they drain, Then each gets its own
    worktree + venv and ALL N end up paid -- zero manual babysitting, zero
    cross-item environment sharing.

    ``assert_state_delta`` pins the port-exposed cleanup invariant: once the
    WHOLE batch settles, the repo's worktree list and HEAD are back to
    EXACTLY what they were before the batch started -- transient per-item
    worktrees never leak past the call that created them.
    """
    # covers: R1
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    item_ids = tuple(f"TD-{n:03d}" for n in range(1, item_count + 1))
    composition.seed_disjoint_pile_items(item_ids)
    env_provision = FakeEnvProvisionPort()
    merge_lock = RecordingMergeLock()
    before = composition.capture_universe()

    batch = composition.run_drain_batch(
        merge_lock=merge_lock, env_provision=env_provision, item_count=item_count
    )

    after = composition.capture_universe()
    assert_state_delta(
        before,
        after,
        universe={"git.worktree_list", "git.head_sha"},
        expected={
            "git.worktree_list": unchanged(),
            "git.head_sha": unchanged(),
        },
    )
    assert set(batch.drained_item_ids) == set(item_ids), (
        f"all {item_count} disjoint items must drain; got "
        f"{batch.drained_item_ids!r} against the seeded population {item_ids!r}"
    )
    for item_id in item_ids:
        assert not composition.pile_contains(item_id)
        assert composition.paid_contains(item_id)
    provisioned = env_provision.provisioned_paths
    assert len(provisioned) == item_count, (
        f"exactly one venv provision per seeded item ({item_count} total); "
        f"got {len(provisioned)}: {provisioned!r}"
    )
    assert len(set(provisioned)) == item_count, (
        "every item's venv must be provisioned at a DISTINCT worktree path -- "
        f"got duplicates in {provisioned!r}"
    )


@pytest.mark.parametrize("item_count", [2, 3])
def test_agent_reasoning_lanes_run_concurrently_while_the_shared_box_serializes(
    tmp_path, item_count
):
    """Given N disjoint items, When they drain, Then ALL N items' agent
    invocations were in-flight AT THE SAME TIME (the reasoning lane is
    parallel) -- proven deterministically via an N-party barrier no fewer
    than N concurrent invocations can pass, never a hope-they-overlap timing
    race.

    Parametrized [2, 3] (peer-review revision): a fixed 2-party barrier could
    pass even if the harness only ever achieves pairwise overlap and silently
    caps concurrency at 2 regardless of batch size -- the N=3 case proves the
    barrier (and therefore the underlying concurrency) genuinely SCALES with
    the item count, not merely "at least two lanes happened to overlap once."

    If the harness serialized agent dispatch (defeating the parallelism this
    slice exists to add), the LAST lane's ``invoke()`` never arrives and the
    barrier times out inside ``run_drain_batch`` before this test body
    resumes -- the timeout IS the failure signal for that regression.

    The barrier is an EXPLICIT opt-in (``barrier_gated_agent_invocation``):
    this is the one AT in this file whose own claim is about lane overlap,
    so it is the one AT that injects it. Every other ``run_drain_batch``
    consumer gets the real adapter with no rendezvous (shard-3 CI fix,
    2026-08-09 -- see ``test_default_batch_composition_wires_the_real_agent_
    invocation_adapter_with_no_barrier`` below).
    """
    # covers: R2
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    item_ids = tuple(f"TD-{n:03d}" for n in range(1, item_count + 1))
    composition.seed_disjoint_pile_items(item_ids)
    env_provision = FakeEnvProvisionPort()
    merge_lock = RecordingMergeLock()

    composition.run_drain_batch(
        merge_lock=merge_lock,
        env_provision=env_provision,
        item_count=item_count,
        agent_invocation=composition.barrier_gated_agent_invocation(parties=item_count),
    )


def test_green_to_green_and_merge_back_never_overlap_across_concurrent_items(
    tmp_path,
):
    """Given 2 disjoint items draining concurrently, When each reaches its
    green-to-green + merge-back step, Then the shared-box critical section
    is NEVER held by two items at once -- the merge lock's own event log
    proves mutual exclusion, not merely "the final state looked fine."

    Negative AT: a batch that let two critical sections overlap could
    corrupt the shared integration branch (design doc §9's whole reason for
    the lock existing) even if, by luck, this run's outcome still looked
    green -- so the invariant is asserted on the LOCK'S OWN witness log, not
    inferred from the final result.
    """
    # covers: R3
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    item_ids = ("TD-001", "TD-002")
    composition.seed_disjoint_pile_items(item_ids)
    env_provision = FakeEnvProvisionPort()
    merge_lock = RecordingMergeLock()

    composition.run_drain_batch(
        merge_lock=merge_lock, env_provision=env_provision, item_count=2
    )

    assert merge_lock.max_concurrent_holders() <= 1, (
        "the merge lock's own event log recorded MORE than one "
        "simultaneously-open critical section -- green-to-green + "
        "merge-back for two items overlapped, exactly the shared-box "
        f"corruption design doc §9 forbids: {merge_lock.events!r}"
    )
    assert merge_lock.acquire_release_counts_balance(), (
        "every acquire must have exactly one matching release (PARTITION "
        f"conservation) -- unbalanced event log: {merge_lock.events!r}"
    )


def test_a_failing_items_broken_change_never_leaks_into_a_sibling_items_worktree(
    tmp_path,
):
    """Given 2 disjoint items where ONE agent breaks its own fast+impacted
    tests, When the batch drains, Then the OTHER item still drains
    successfully and its worktree/commit carries ZERO trace of the failing
    item's change -- the false-green oracle's isolation half.

    Negative AT: the failing item must NOT vanish silently (the charter's
    "unsafe item silently DROPPED" oracle) -- it stays in techdebt.md,
    un-drained, its own worktree cleaned up like every refusal path.
    """
    # covers: R4
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    item_ids = ("TD-BREAKS", "TD-SAFE")
    composition.seed_disjoint_pile_items(item_ids)
    composition.seed_toy_passing_test()
    env_provision = FakeEnvProvisionPort()
    merge_lock = RecordingMergeLock()

    batch = composition.run_drain_batch(
        merge_lock=merge_lock,
        env_provision=env_provision,
        item_count=2,
        agent_cmd=composition.agent_cmd_that_breaks_the_test_suite(),
    )

    results_by_id = {result.item_id: result for result in batch.results}
    assert results_by_id["TD-BREAKS"].drained is False, (
        "an item whose own change breaks its test suite must never be "
        "reported as drained -- false-green"
    )
    assert composition.pile_contains("TD-BREAKS"), (
        "a refused item must remain visible in techdebt.md, never "
        "silently dropped from BOTH pile files"
    )
    assert not composition.paid_contains("TD-BREAKS")
    assert not composition.branch_exists("refactor-TD-BREAKS"), (
        "mandatory per-item cleanup applies on the refusal path too -- "
        "no leftover branch for the failing item"
    )


def test_two_concurrent_merges_never_drop_either_items_commit_from_the_integration_branch(
    tmp_path,
):
    """Given 2 disjoint items that BOTH succeed, When they merge back
    concurrently (serialized behind the lock), Then the integration
    branch's final tree carries BOTH items' distinct file changes -- a
    lost-update race (one merge silently overwriting the other) never
    drops a confirmed item's commit.

    COUNT/PARTITION closure: the population is the 2 seeded items; the
    integration branch's tracked-paths set is asserted to CONTAIN both
    items' distinct marker files, not merely "at least one."
    """
    # covers: R5
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    item_ids = ("TD-001", "TD-002")
    composition.seed_disjoint_pile_items(item_ids)
    env_provision = FakeEnvProvisionPort()
    merge_lock = RecordingMergeLock()

    batch = composition.run_drain_batch(
        merge_lock=merge_lock, env_provision=env_provision, item_count=2
    )

    assert len(batch.drained_item_ids) == len(item_ids), (
        f"expected all {len(item_ids)} seeded items merged; got "
        f"{batch.drained_item_ids!r}"
    )
    tracked = composition.integration_branch_tracked_paths()
    for item_id in item_ids:
        assert f"fixed-{item_id}.txt" in tracked, (
            f"{item_id}'s own commit is missing from the integration "
            f"branch's final tree -- a concurrent merge silently dropped "
            f"it. Tracked paths: {tracked!r}"
        )


@pytest.mark.parametrize("batch_kind", ["plain", "selector-injected"])
def test_default_batch_composition_wires_the_real_agent_invocation_adapter_with_no_barrier(
    tmp_path, batch_kind
):
    """Given no explicit ``agent_invocation`` override, When either batch
    composition root is built (``drain_service_for_batch`` -- ``run_drain_batch``'s
    default; ``drain_service_for_batch_with_selector`` -- scenario 5's
    ``observe_reported_scope_for_batch``), Then the REAL
    ``ShellAgentInvocationAdapter`` is wired directly -- never a
    barrier-gated wrapper.

    Regression witness for a real CI failure (shard-3, 2026-08-09) and its
    independent-review follow-up: ``BarrierGatedAgentInvocationPort.
    wait(timeout=10)`` used to wrap EVERY batch consumer of BOTH
    construction sites unconditionally, so an ordinary batch AT with no
    interest in reasoning-lane overlap could time out under xdist
    contention (unbounded real ``git worktree`` subprocesses on a 4-vCPU
    runner). The barrier is now an explicit opt-in
    (``barrier_gated_agent_invocation``) that only
    ``test_agent_reasoning_lanes_run_concurrently_while_the_shared_box_serializes``
    injects. This test asserts BOTH default compositions never reintroduce
    the rendezvous -- structurally, with no thread, no subprocess, and no
    11-second sleep needed to prove it.
    """
    composition = RefactorSwarmComposition(tmp_path)
    merge_lock = RecordingMergeLock()
    env_provision = FakeEnvProvisionPort()

    if batch_kind == "plain":
        port_type_name = composition.default_batch_agent_invocation_type_name(
            merge_lock=merge_lock, env_provision=env_provision
        )
    else:
        port_type_name = (
            composition.default_batch_with_selector_agent_invocation_type_name(
                selector=None, merge_lock=merge_lock, env_provision=env_provision
            )
        )

    assert port_type_name == "ShellAgentInvocationAdapter", (
        f"the default {batch_kind!r} batch composition must wire the real "
        "shell adapter directly -- a BarrierGatedAgentInvocationPort here "
        "would reintroduce the shard-3 CI hazard (an artificial rendezvous "
        f"unconditionally wrapped around every ordinary batch consumer); "
        f"got {port_type_name!r}"
    )
