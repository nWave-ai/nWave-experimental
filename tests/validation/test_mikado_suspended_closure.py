"""A closure standing on an open node has a state, and it is not a closed one.

Two nodes reached the tree with their work finished and their foundation still
open. `FATTO` overstated them -- it reports a closure standing on nothing, which
is exactly what `closed-over-open-child` exists to reject -- and `PRONTO` erased
work that genuinely happened, sending the next reader to redo it. The vocabulary
had no third word, so the document became unwritable rather than say something
false.

`<closing word>-SOSPESO` is that third word, and `FUSO IN X` is the neighbouring
case: a node whose work was folded into another one has closed nothing until the
node it fused INTO closes. Both must read OPEN, in the gate AND on the board --
a suspended closure that counted as closed would be the same overstatement, one
token further along.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "validation"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import mikado_board as board
from validate_mikado_tree_coherence import (
    CLOSED_STATES,
    SUSPENDED_STATES,
    ClosureClass,
    _state_token_in,
    check_closed_over_open_child,
    classify_state,
    fusion_target,
    resolve_fusions,
)


REGISTER = "2026-07-28-decisions-consolidated.md"


def _tree_with_register(tmp_path: Path, rows: list[tuple[str, str]]) -> Path:
    """Write a doc plus the register the gate reads its edges from."""
    # `dipende-da` must land on cells[7], the column the gate reads.
    header = (
        "| Nodo | a | b | c | d | e | dipende-da |\n|---|---|---|---|---|---|---|\n"
    )
    body = "".join(f"| {n} | . | . | . | . | . | {cell} |\n" for n, cell in rows)
    (tmp_path / REGISTER).write_text(header + body)
    doc = tmp_path / "tree.md"
    doc.write_text("# tree\n")
    return doc


# --------------------------------------------------------------------------
# the suspended closure is OPEN, everywhere
# --------------------------------------------------------------------------


@pytest.mark.parametrize("suspended", sorted(SUSPENDED_STATES))
def test_a_suspended_closure_is_open_never_closed(suspended):
    """Whatever word closes a node, suspending it re-opens it.

    The mirror of `BLOCCATO-SERVE-DESIGN`: a state the legend does not classify
    OPEN is a state that can be read as finished.
    """
    assert classify_state(suspended) is ClosureClass.OPEN


def test_every_closing_word_has_a_suspended_form():
    """Generated, not typed: a hand-kept list grows a gap at the seventh word."""
    assert frozenset(f"{w}-SOSPESO" for w in CLOSED_STATES) == SUSPENDED_STATES
    assert len(SUSPENDED_STATES) == len(CLOSED_STATES)


def test_suspended_never_collapses_onto_the_closing_word_it_contains():
    """`FATTO-SOSPESO` starts with `FATTO`; a prefix scan would call it closed."""
    assert classify_state("FATTO-SOSPESO") is not ClosureClass.CLOSED
    assert _state_token_in("FATTO-SOSPESO") == "FATTO-SOSPESO"
    assert _state_token_in("MISURATO-SOSPESO") == "MISURATO-SOSPESO"


def test_a_suspended_parent_over_an_open_child_passes(tmp_path):
    """The whole point: the honest state passes where the overstatement failed."""
    doc = _tree_with_register(tmp_path, [("D48", "D03")])
    states = {"D48": classify_state("FATTO-SOSPESO"), "D03": ClosureClass.OPEN}

    assert check_closed_over_open_child(doc, states) == []


def test_the_same_parent_declared_fatto_is_still_rejected(tmp_path):
    """The rule did not get looser -- only the vocabulary got truer."""
    doc = _tree_with_register(tmp_path, [("D48", "D03")])
    states = {"D48": ClosureClass.CLOSED, "D03": ClosureClass.OPEN}

    findings = check_closed_over_open_child(doc, states)

    assert [f.rule for f in findings] == ["closed-over-open-child"]
    assert "D03" in findings[0].what


# --------------------------------------------------------------------------
# fusion carries the target's state, it does not have one of its own
# --------------------------------------------------------------------------


def test_a_fusion_names_the_node_it_defers_to():
    assert fusion_target("FUSO IN D03b") == "D03B"
    assert fusion_target("fuso in d47") == "D47"
    assert fusion_target("FATTO") is None


def test_a_fusion_keeps_its_target_through_the_token_scanner():
    """`FUSO` alone would name a deferral without saying what it defers TO.

    Losing the target is not cosmetic: with the word unknown, the column-drift
    rescue in the node-table parser walked past the `Stato` cell and read D47's
    state out of the `Verdetto` column next door.
    """
    assert _state_token_in("FUSO IN D03b") == "FUSO IN D03B"


def test_fused_into_an_open_node_has_closed_nothing():
    resolved = resolve_fusions(
        {"D47": ClosureClass.OPEN, "D03B": ClosureClass.OPEN},
        {"D47": "D03B", "D03B": None},
    )

    assert resolved["D47"] is ClosureClass.OPEN


def test_fused_into_a_closed_node_closes_with_it():
    resolved = resolve_fusions(
        {"D47": ClosureClass.OPEN, "D03B": ClosureClass.CLOSED},
        {"D47": "D03B", "D03B": None},
    )

    assert resolved["D47"] is ClosureClass.CLOSED


def test_a_chain_of_fusions_resolves_at_its_end():
    resolved = resolve_fusions(
        {"A1": ClosureClass.OPEN, "B2": ClosureClass.OPEN, "C3": ClosureClass.CLOSED},
        {"A1": "B2", "B2": "C3", "C3": None},
    )

    assert resolved["A1"] is ClosureClass.CLOSED
    assert resolved["B2"] is ClosureClass.CLOSED


def test_a_ring_of_fusions_closes_nothing():
    """Two nodes each deferring to the other have delivered nothing between them."""
    resolved = resolve_fusions(
        {"A1": ClosureClass.OPEN, "B2": ClosureClass.OPEN},
        {"A1": "B2", "B2": "A1"},
    )

    assert resolved["A1"] is ClosureClass.OPEN
    assert resolved["B2"] is ClosureClass.OPEN


def test_a_fusion_into_a_node_the_document_does_not_carry_stays_open():
    """The safe direction: the alternative is a closure nobody can point at."""
    resolved = resolve_fusions({"D47": ClosureClass.OPEN}, {"D47": "D99"})

    assert resolved["D47"] is ClosureClass.OPEN


def test_a_parent_over_a_fusion_into_an_open_node_is_still_rejected(tmp_path):
    """D49 waited for D47, and D47 was `FUSO IN D03b` while D03b was open.

    Fusion is a forward deferral, not a closure -- so the parent above it is
    closed over something open, and the rule must still fire.
    """
    doc = _tree_with_register(tmp_path, [("D49", "D47"), ("D47", "NONE")])
    states = resolve_fusions(
        {
            "D49": ClosureClass.CLOSED,
            "D47": ClosureClass.OPEN,
            "D03B": ClosureClass.OPEN,
        },
        {"D47": "D03B"},
    )

    findings = check_closed_over_open_child(doc, states)

    assert [f.rule for f in findings] == ["closed-over-open-child"]
    assert "D47" in findings[0].what


# --------------------------------------------------------------------------
# the board and the gate must say the same thing
# --------------------------------------------------------------------------


def test_the_board_never_draws_as_closed_what_the_gate_calls_open():
    """The divergence that hid seven nodes, asserted away.

    A state the board paints closed while the gate classifies it open is an
    overstatement nobody reports -- exactly how D47 rendered as done (`[>]`, a
    closed glyph) while the gate read it as still open.
    """
    # The bad classes are OPEN (work still to do, painted as finished) and UNKNOWN
    # (the gate cannot say, and the board says "done" anyway). NOT_WORK is neither:
    # `GUARDIA` marks a standing invariant rather than a unit of work, so drawing it
    # alongside the closed rows overstates nothing -- there is no work to overstate.
    overstated = [
        (state, glyph, classify_state(state).value)
        for state, (glyph, _rank) in board.STATE_GLYPH.items()
        # `FUSO IN` resolves against ANOTHER node rather than on its own, so it is
        # covered by the fusion tests above instead of by this static sweep.
        if glyph in board.CLOSED_GLYPHS
        and state != "FUSO IN"
        and classify_state(state) in (ClosureClass.OPEN, ClosureClass.UNKNOWN)
    ]

    assert overstated == []


@pytest.mark.parametrize("suspended", sorted(SUSPENDED_STATES))
def test_the_board_draws_a_suspended_closure_as_open(suspended):
    glyph, _rank = board._glyph(suspended)

    assert glyph not in board.CLOSED_GLYPHS


def test_the_board_matches_the_longest_state_word_not_the_first(tmp_path):
    """Dict order made `FATTO-SOSPESO` match `FATTO` and draw as finished."""
    assert board._glyph("FATTO-SOSPESO")[0] != board._glyph("FATTO")[0]
    assert board._glyph("MISURATO-SOSPESO")[0] != board._glyph("MISURATO")[0]


def test_the_board_draws_a_fusion_into_an_open_node_as_open():
    states = {"D47": ("FUSO IN D03b", "t"), "D03B": ("BLOCCATO-SERVE-DESIGN", "t")}

    glyph, _rank = board._glyph("FUSO IN D03b", states)

    assert glyph not in board.CLOSED_GLYPHS


def test_the_board_draws_a_fusion_into_a_closed_node_as_closed():
    states = {"D47": ("FUSO IN D03b", "t"), "D03B": ("FATTO", "t")}

    glyph, _rank = board._glyph("FUSO IN D03b", states)

    assert glyph in board.CLOSED_GLYPHS


def test_the_board_never_loops_on_a_ring_of_fusions():
    states = {"A1": ("FUSO IN B2", "t"), "B2": ("FUSO IN A1", "t")}

    glyph, _rank = board._glyph("FUSO IN B2", states)

    assert glyph not in board.CLOSED_GLYPHS
