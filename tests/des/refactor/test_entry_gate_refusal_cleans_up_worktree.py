# @feature-des-refactor-fixer-swarm
# @slice-01
"""Regression test -- bugfix-refactor-entry-gate-worktree-leak.

RCA (feature-end EXAMINE, ``nw-user-examiner`` black-box CLI run):
``RefactorDrainService.drain_one``'s entry-gate refusal path
(``_entry_gate_refusal``, called from ``drain_one`` BEFORE the
green-to-green/merge step) returned early via a bare ``self._refused(...)``
``DrainResult`` on EVERY refusal branch (``EntryGateVerdictMissing`` /
``MikadoEscalation`` / the no-test-net verdicts) WITHOUT ever calling
``self._git_worktree.remove_worktree`` or ``delete_branch`` -- unlike the
red-tests and merge-failure refusal paths a few lines below in the same
method, which both clean up before returning. A live `des refactor` run
left a stray worktree + a stray ``refactor-<item-id>`` branch behind after
an entry-gate refusal, violating slice-01's own walking-skeleton charter
("when the run is over the repository looks like nobody was ever there").

Layer 3 composition (in-process, L2 default), same driving surface every
other slice-01/slice-04 AT in this directory already uses:
``RefactorSwarmComposition.run_drain_one_item`` drives
``RefactorDrainService.drain_one`` directly with the REAL production
adapters wired in (Pillar 3).
"""

from __future__ import annotations

import pytest

from .composition import RefactorSwarmComposition
from .domain_types import EntryGateAgentVerdict


pytestmark = pytest.mark.acceptance

_ENTRY_GATE_VERDICT_MISSING = "EntryGateVerdictMissing"
_MIKADO_ESCALATION_REASON = "MikadoEscalation"
_NO_TEST_NET_REASON = "EntryGateNoTestNet"


def test_entry_gate_refusal_removes_worktree_and_branch(tmp_path):
    """Given an item whose agent emits NO recognized entry-gate verdict
    token, When the drain refuses the item at the entry gate, Then the
    item's worktree AND branch are BOTH removed -- an entry-gate refusal
    must leave the repository exactly as clean as a red-tests or
    merge-failure refusal already does.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    composition.seed_toy_passing_test()
    composition.seed_pile_item(item_id="TD-001")

    result = composition.run_drain_one_item(
        agent_cmd=composition.agent_cmd_emitting_no_recognized_verdict()
    )

    assert result.merged is False
    assert result.merge_blocked_reason == _ENTRY_GATE_VERDICT_MISSING
    assert result.worktree_removed is True, (
        "an entry-gate refusal must remove the item's worktree, exactly "
        "like a red-tests or merge-failure refusal does"
    )
    assert result.branch_deleted is True, (
        "an entry-gate refusal must delete the item's branch, exactly "
        "like a red-tests or merge-failure refusal does"
    )
    assert "TD-001" not in composition.worktree_list(), (
        "git worktree list must show no dangling registration after an "
        "entry-gate refusal -- a stray worktree was left behind"
    )
    assert not composition.branch_exists("refactor-TD-001"), (
        "the item's refactor-TD-001 branch must no longer exist after an "
        "entry-gate refusal -- a stray branch was left behind"
    )


@pytest.mark.parametrize(
    ("verdict", "expected_reason"),
    [
        (EntryGateAgentVerdict.MIKADO_ESCALATION, _MIKADO_ESCALATION_REASON),
        (EntryGateAgentVerdict.CHARACTERIZE_FIRST, _NO_TEST_NET_REASON),
        (EntryGateAgentVerdict.ABSTAINED, _NO_TEST_NET_REASON),
    ],
    ids=["mikado-escalation", "characterize-first", "abstained"],
)
def test_every_entry_gate_refusal_branch_removes_worktree_and_branch(
    tmp_path, verdict: EntryGateAgentVerdict, expected_reason: str
):
    """Given an item whose agent emits ``verdict`` (Mikado escalation, or one
    of the no-test-net verdicts), When the drain refuses the item at the
    entry gate, Then the item's worktree AND branch are both removed --
    covers all THREE named entry-gate refusal branches
    (``EntryGateVerdictMissing`` is covered by the sibling test above),
    matching the RCA's own enumeration.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    composition.seed_toy_passing_test()
    composition.seed_pile_item(item_id="TD-001")

    result = composition.run_drain_one_item(
        agent_cmd=composition.agent_cmd_emitting_verdict(verdict)
    )

    assert result.merged is False
    assert result.merge_blocked_reason == expected_reason
    assert result.worktree_removed is True, (
        f"a {verdict.value} entry-gate refusal must remove the item's worktree"
    )
    assert result.branch_deleted is True, (
        f"a {verdict.value} entry-gate refusal must delete the item's branch"
    )
    assert "TD-001" not in composition.worktree_list(), (
        f"git worktree list must show no dangling registration after a "
        f"{verdict.value} entry-gate refusal"
    )
    assert not composition.branch_exists("refactor-TD-001"), (
        f"the item's refactor-TD-001 branch must no longer exist after a "
        f"{verdict.value} entry-gate refusal"
    )
