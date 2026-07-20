"""AT-7 (D9 entry gate) + AT-8 (D9 Mikado escalation) -- slice-04
(des-refactor-fixer-swarm). Value statement (feature-delta Slice Plan):
"An item with NO real observable test net refuses to be refactored blind --
it is characterized first or explicitly abstained; an item whose own agent
escalates to Mikado is NOT merged, NOT moved to `paidtechdebt.md`, and is
annotated `escalated` for human follow-up."

@driving_port @contract-shape:bounded-change

Layer 3 composition (in-process, L2 default) throughout -- drives
``RefactorDrainService.drain_one`` directly with the real production
adapters (Pillar 3), exactly as every non-walking-skeleton slice-01 AT does.
No new driving surface: the entry gate is a PRE-merge classification inside
the SAME ``drain_one`` lifecycle slice-01 already exercises end to end.

RED-scaffold note: ``des.domain.refactor.entry_gate.classify_entry_gate`` is
a Mandate-7 RED scaffold (raises ``AssertionError``) and is NOT YET wired
into ``RefactorDrainService.drain_one`` -- that wiring is A_GREEN's job
(feature-delta: "Slice-04 wires `AgentInvocationResult.stdout` into
`classify_entry_gate` BEFORE the green-to-green/merge step"). Every scenario
below is therefore active-RED TODAY for a DIFFERENT, still-correct reason:
``drain_one`` has no entry-gate check at all yet, so a well-behaved stand-in
agent (green tests, no real code damage) merges regardless of what it prints
on stdout -- the exact "silently 'verified' against a vacuous/unclassified
green" failure mode this slice exists to close. Each ``Then`` below asserts
the outcome slice-04 must produce; today's actual outcome (an unconditional
merge) fails those assertions -- MISSING_FUNCTIONALITY, the correct RED
classification (never IMPORT_ERROR/FIXTURE_BROKEN).

Known cross-slice coherence flag (see this feature's DISTILL handoff report,
also pinned in ``test_slice_01_safety_and_isolation.py``'s own "vacuous-green
... NOT authored here" charter note): slice-01's existing ATs default their
stand-in agent to ``agent_cmd="true"`` (empty stdout, no verdict token at
all). Once A_GREEN wires the entry gate in literally, those pre-existing
slice-01 scenarios will ALSO carry no recognized verdict token and will
regress to ``EntryGateVerdictMissing`` refusal unless A_GREEN additionally
updates their stand-in agent to emit ``REFACTOR_SAFE``. This file does NOT
touch any slice-01 test -- that coordination is explicitly flagged forward,
not silently resolved here (Given-fixture ownership boundary).
"""

from __future__ import annotations

import pytest

from .composition import RefactorSwarmComposition
from .domain_types import EntryGateAgentVerdict


pytestmark = pytest.mark.acceptance

_ENTRY_GATE_VERDICT_MISSING = "EntryGateVerdictMissing"


def test_item_with_no_recognized_entry_gate_verdict_refuses_merge_and_never_reaches_paidtechdebt(
    tmp_path,
):
    """AT-7, negative -- Given the agent's own output carries NO recognized
    entry-gate verdict token (free-form commentary only), When the item's
    fast+impacted tests come back green anyway, Then merge-back refuses with
    the NAMED ``EntryGateVerdictMissing`` outcome -- never a silent merge
    against an unclassified green, and the item is never moved to
    ``paidtechdebt.md``.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    composition.seed_toy_passing_test()
    composition.seed_pile_item(item_id="TD-001")

    result = composition.run_drain_one_item(
        agent_cmd=composition.agent_cmd_emitting_no_recognized_verdict()
    )

    assert result.merged is False, (
        "an item whose agent output carries no recognized entry-gate "
        "verdict token must NEVER be merged, even when its tests stay green"
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
        "recorded in paidtechdebt.md -- never a silent merge"
    )


def test_a_missing_entry_gate_verdict_refuses_even_when_the_pile_has_no_real_tests_at_all(
    tmp_path,
):
    """AT-7, negative (vacuous-green companion) -- Given the item's worktree
    carries NO real test at all (a genuinely vacuous 0-collected green) AND
    the agent emits no recognized verdict token, Then merge-back still
    refuses with ``EntryGateVerdictMissing`` -- the entry gate's refusal does
    not depend on tests existing; it depends on the agent's OWN self-reported
    classification being present and recognized.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    composition.seed_pile_item(item_id="TD-001")

    result = composition.run_drain_one_item(
        agent_cmd=composition.agent_cmd_emitting_no_recognized_verdict()
    )

    assert result.merged is False, (
        "a vacuous (0-collected) green must never be treated as license to "
        "merge when the agent never classified the item's own test net"
    )
    assert result.merge_blocked_reason == _ENTRY_GATE_VERDICT_MISSING, (
        f"expected EntryGateVerdictMissing; got {result.merge_blocked_reason!r}"
    )


def test_mikado_escalation_verdict_is_never_merged_and_never_moved_to_paidtechdebt(
    tmp_path,
):
    """AT-8, negative -- Given the item's own agent emits ``MIKADO_ESCALATION``
    on its output, When the drain evaluates the entry gate, Then the item is
    NOT merged and NOT moved to ``paidtechdebt.md`` -- it stays in
    ``techdebt.md``, annotated ``escalated`` for human follow-up (D9).
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    composition.seed_toy_passing_test()
    composition.seed_pile_item(item_id="TD-001")

    result = composition.run_drain_one_item(
        agent_cmd=composition.agent_cmd_emitting_verdict(
            EntryGateAgentVerdict.MIKADO_ESCALATION
        )
    )

    assert result.merged is False, (
        "a Mikado-escalated item must NEVER be merged -- escalation is not a merge path"
    )
    assert result.drained is False, (
        "a Mikado-escalated item must never be reported as drained"
    )
    assert not composition.paid_contains("TD-001"), (
        "a Mikado-escalated item must NEVER be moved to paidtechdebt.md"
    )
    assert composition.pile_contains("TD-001"), (
        "a Mikado-escalated item must stay visible in techdebt.md for "
        "human follow-up, never silently disappear"
    )
    assert composition.techdebt_item_annotated_escalated("TD-001"), (
        "a Mikado-escalated item must be ANNOTATED 'escalated' in "
        "techdebt.md in place -- a bare unmodified pending entry is "
        "indistinguishable from an ordinary un-drained item and loses the "
        "human-follow-up signal"
    )


def test_mikado_escalation_is_never_silently_indistinguishable_from_an_ordinary_pending_item(
    tmp_path,
):
    """AT-8, negative (silently-dropped oracle) -- Given TWO items are seeded
    and only ONE agent escalates to Mikado, Then the escalated item's own
    pending line is annotated ``escalated`` while an ordinary un-drained
    sibling is not -- the escalation signal must be item-specific, never a
    pile-wide side effect that would make a genuinely-unsafe item
    indistinguishable from a merely-not-yet-attempted one.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    composition.seed_toy_passing_test()
    composition.seed_pile_item(item_id="TD-001")
    composition.pile_path.write_text(
        composition.pile_path.read_text(encoding="utf-8")
        + '- [ ] TD-002: paradigm=object-oriented defect="unrelated debt" '
        'proposed_solution="unrelated fix"\n',
        encoding="utf-8",
    )

    composition.run_drain_one_item(
        agent_cmd=composition.agent_cmd_emitting_verdict(
            EntryGateAgentVerdict.MIKADO_ESCALATION
        )
    )

    assert composition.techdebt_item_annotated_escalated("TD-001"), (
        "TD-001 (the item whose agent escalated) must carry the 'escalated' annotation"
    )
    assert not composition.techdebt_item_annotated_escalated("TD-002"), (
        "TD-002 (an unrelated, un-drained sibling item) must NOT be "
        "annotated 'escalated' -- the signal must be item-specific, never "
        "a pile-wide side effect"
    )


@pytest.mark.parametrize(
    "verdict",
    [EntryGateAgentVerdict.CHARACTERIZE_FIRST, EntryGateAgentVerdict.ABSTAINED],
    ids=["characterize-first", "abstained"],
)
def test_no_test_net_verdicts_refuse_to_merge_blind_and_never_reach_paidtechdebt(
    tmp_path, verdict: EntryGateAgentVerdict
):
    """AT-7 family, negative -- Given the agent classifies the item as
    needing characterization first, or explicitly abstains, When the drain
    evaluates the entry gate, Then the item is NOT merged and NOT moved to
    ``paidtechdebt.md`` -- "characterized first or explicitly abstained,
    never silently 'verified' against a vacuous green" (Value statement #4).
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    composition.seed_toy_passing_test()
    composition.seed_pile_item(item_id="TD-001")

    result = composition.run_drain_one_item(
        agent_cmd=composition.agent_cmd_emitting_verdict(verdict)
    )

    assert result.merged is False, (
        f"an item classified {verdict.value} must never be refactored "
        "blind -- it must never merge"
    )
    assert not composition.paid_contains("TD-001"), (
        f"an item classified {verdict.value} must NEVER be moved to paidtechdebt.md"
    )
    assert composition.pile_contains("TD-001"), (
        f"an item classified {verdict.value} must stay visible in "
        "techdebt.md, never silently vanish"
    )
