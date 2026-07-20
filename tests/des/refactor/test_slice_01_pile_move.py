# @feature-des-refactor-fixer-swarm
# @slice-01
"""Pile-move -- slice-01 (Slice Plan Value statement: `techdebt.md` -> `paidtechdebt.md`).

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


def test_a_drained_item_moves_from_techdebt_to_paidtechdebt(tmp_path):
    """Positive -- Given a pending item, When it drains and merges, Then it is
    removed from `techdebt.md` and recorded in `paidtechdebt.md`.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    composition.seed_pile_item(item_id="TD-001")

    result = composition.run_drain_one_item()

    assert result.drained is True
    assert result.item_id == "TD-001"
    assert not composition.pile_contains("TD-001"), (
        "a drained item must be removed from techdebt.md"
    )
    assert composition.paid_contains("TD-001"), (
        "a drained item must be recorded in paidtechdebt.md"
    )


def test_an_item_never_moves_to_paidtechdebt_when_the_merge_never_confirmed(
    tmp_path,
):
    """Negative -- Given a drain's merge is refused (dirty integration tree),
    Then the item is NOT moved to `paidtechdebt.md` and STAYS in
    `techdebt.md` -- a failed drain must never be falsely marked paid.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_dirty_integration_branch()
    composition.seed_pile_item(item_id="TD-001")

    result = composition.run_drain_one_item()

    assert result.drained is False
    assert composition.pile_contains("TD-001"), (
        "an item whose merge was refused must stay in techdebt.md"
    )
    assert not composition.paid_contains("TD-001"), (
        "an item whose merge was refused must NEVER be recorded in "
        "paidtechdebt.md -- a failed drain must never be falsely marked paid"
    )
