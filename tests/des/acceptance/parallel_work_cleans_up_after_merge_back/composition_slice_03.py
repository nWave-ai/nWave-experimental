"""Composition-root extension for parallel-work-cleans-up-after-merge-back
slice-03 (a bugfix's cleanup never waits on a feature-end it doesn't owe --
charter `a-bugfixs-cleanup-never-waits-on-a-feature-end-it-doesnt-owe.md`,
feature-delta Slice Plan row slice-03, Locked Decisions D-4/D-5, ADR-SWARM-002).

REUSES the SAME mechanism slice-01 introduces -- the SHIPPED
`des verify-worktree-cleanup` CLI, `WorktreeCleanupService`, and the SAME
`WorktreeCleanupFixture` trunk-repo + linked-worktree provisioning
(feature-delta D-D6: "this service never imports or touches
AtCompletionLedgerPort... protected BY CONSTRUCTION"). Slice-01's own
AT-CLEANUP-5 already pins the WRITE-side half of D-D6 (a sweep never
*appends* a FeatureEndPending record) inside every one of its 5 scenarios.
The facet slice-01 never exercised is the READ/WAIT-side half the charter's
own oracle names explicitly: a feature-end-pending record ALREADY sitting in
the ledger (for an unrelated unit of work) must neither block, delay, nor
alter this unit of work's own cleanup outcome, for EITHER a bugfix-flavored
or a feature-slice-flavored worktree (D-5 uniformity -- no persona
special-casing). `PendingFeatureEndFixture` adds exactly ONE new capability
slice-01 never needed -- seeding a pre-existing `FeatureEndPending` ledger
record BEFORE the sweep runs -- and reuses every other fixture method
(`build_trunk_repo`, `create_linked_worktree`, `confirm_merge_back`,
`run_sweep_in_process`) verbatim.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger

from .composition_slice_01 import WorktreeCleanupFixture


_FEATURE_END_PENDING_EVENT = "FeatureEndPending"
_UNRELATED_FEATURE_ID = "an-unrelated-feature-already-mid-feature-end"


class PendingFeatureEndFixture(WorktreeCleanupFixture):
    """Extends slice-01's fixture with the ONE capability slice-03's
    decoupling oracle needs and slice-01 never needed: seeding a
    pre-existing `FeatureEndPending` ledger record BEFORE a sweep runs, so
    the sweep's own outcome can be checked for independence from it.

    Pillar 3 unchanged: same real trunk repo, same SHIPPED
    `GitWorktreeAdapter` substrate, same production `des
    verify-worktree-cleanup` driving surface -- this slice differs ONLY in
    the ledger PRECONDITION it seeds before invoking that same mechanism.
    """

    def ensure_trunk_repo(self) -> None:
        """Idempotent: builds the trunk repo only if it does not already
        exist. Slice-03's two Given steps (pending-record-seed,
        persona-worktree) can chain in either order and both need the SAME
        repo to exist exactly once -- `build_trunk_repo` itself is NOT
        idempotent (a second `git commit`/`git branch -m` would error)."""
        if not self._repo.exists():
            self.build_trunk_repo()

    def seed_existing_feature_end_pending(self) -> None:
        """Append ONE `FeatureEndPending` record for an UNRELATED feature --
        simulating "some other unit of work already triggered feature-end
        eligibility" -- entirely independent of the worktree(s) this
        scenario's sweep will evaluate."""
        self.ensure_trunk_repo()
        ledger = AtCompletionLedger(project_root=self._repo)
        ledger.append_gate_event(
            _FEATURE_END_PENDING_EVENT, "", feature_id=_UNRELATED_FEATURE_ID
        )

    def feature_end_pending_count(self) -> int:
        """Public wrapper the step layer reads directly (never reaches past
        the fixture into the ledger itself -- Mandate-12 criterion 3)."""
        return self._feature_end_pending_count()


@pytest.fixture
def cleanup_fixture(tmp_path: Path) -> PendingFeatureEndFixture:
    """This slice's composition-root service -- the EXTENDED fixture, bound
    to the SAME `cleanup_fixture` name slice-01's reused Given/When steps
    expect."""
    return PendingFeatureEndFixture(tmp_path)


__all__ = ["PendingFeatureEndFixture", "cleanup_fixture"]
