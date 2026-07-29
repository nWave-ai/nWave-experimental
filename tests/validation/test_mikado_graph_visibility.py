"""Acceptance tests: no node of real work may be invisible in every view.

`D27` was in the tables and in nobody's field of view. The cause was not a
missing edge and not a detached subgraph: the register's `dipende-da` cell for
D27 reads `NONE -- e' **prerequisito** di D44 ... e di D20-lato-B`, and the edge
reader took every `D\\d+` token in the cell as a dependency. That inverts the
arrow -- D44 waits for D27, not the other way round -- and the invented arrows
closed a cycle. Every member of a cycle is waited-for by another member, so none
of them is a root, and a renderer that walks down from the roots drops the whole
component in silence.

Same defect class as everywhere else in this file's neighbourhood: decide on the
DESIGNATION (an id appears in the cell) instead of the PROPERTY (this cell
declares a wait).

These tests pin:
- a cell that says NONE and then names ids yields NO edges, and is reported;
- a cell that states the inverse relation yields NO edges, and is reported;
- a clean cell still yields its edges;
- a real cycle is a rejection that names its members;
- a state word outside the legend leaves the node VISIBLE and unverifiable,
  never dropped from the population;
- a dependency on a split node resolves to its sub-slices whatever the case.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = PROJECT_ROOT / "scripts" / "validation"
sys.path.insert(0, str(SCRIPT_DIR))

from validate_mikado_tree_coherence import (
    ClosureClass,
    Severity,
    check_closed_over_open_child,
    check_node_visible_from_a_root,
    classify_state,
    read_dependency_edges,
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
# the edge reader
# --------------------------------------------------------------------------


def test_a_clean_cell_still_yields_its_edges(tmp_path):
    doc = _tree_with_register(tmp_path, [("D49", "D47"), ("D46", "D49 + D03")])

    edges, undecidable = read_dependency_edges(doc)

    assert edges["D49"] == {"D47"}
    assert edges["D46"] == {"D49", "D03"}
    assert undecidable == {}


def test_a_cell_saying_none_never_yields_the_ids_it_mentions(tmp_path):
    """`NONE (beneficia di D03)` is not a dependency on D03."""
    doc = _tree_with_register(tmp_path, [("D17", "NONE (beneficia di D03)")])

    edges, undecidable = read_dependency_edges(doc)

    assert "D17" not in edges
    assert "D03" in undecidable["D17"]


def test_a_cell_stating_the_inverse_relation_never_yields_an_edge(tmp_path):
    """`e' prerequisito di D33` means D33 waits for D21, not D21 for D33."""
    doc = _tree_with_register(tmp_path, [("D21", "e' prerequisito di D33")])

    edges, undecidable = read_dependency_edges(doc)

    assert "D21" not in edges
    assert "D33" in undecidable["D21"]


def test_an_anti_affinity_is_not_a_dependency(tmp_path):
    doc = _tree_with_register(
        tmp_path, [("D31", "NONE tecnicamente. **NON avviare insieme a D22**")]
    )

    edges, _ = read_dependency_edges(doc)

    assert "D31" not in edges


def test_a_cell_naming_nothing_is_a_decided_empty_set_not_undecidable(tmp_path):
    doc = _tree_with_register(tmp_path, [("D27", "NONE")])

    edges, undecidable = read_dependency_edges(doc)

    assert edges["D27"] == set()
    assert undecidable == {}


# --------------------------------------------------------------------------
# visibility
# --------------------------------------------------------------------------


def test_a_cycle_is_rejected_and_names_its_members(tmp_path):
    doc = _tree_with_register(tmp_path, [("D20", "D27"), ("D27", "D20")])
    states = {"D20": ClosureClass.OPEN, "D27": ClosureClass.OPEN}

    findings = check_node_visible_from_a_root(doc, states)

    cycles = [f for f in findings if f.rule == "dependency-cycle-hides-nodes"]
    assert len(cycles) == 1
    assert cycles[0].severity is Severity.REJECT
    assert "D20" in cycles[0].what and "D27" in cycles[0].what


def test_the_real_register_shape_leaves_d27_visible(tmp_path):
    """The exact D27/D20/D44 shape that hid three nodes, read correctly."""
    doc = _tree_with_register(
        tmp_path,
        [
            ("D27", "NONE — è **prerequisito** di D44 e di D20-lato-B"),
            ("D20", "NONE (C) · D03+D27 (B)"),
            ("D44", "**D27**"),
        ],
    )
    states = dict.fromkeys(["D27", "D20", "D44"], ClosureClass.OPEN)

    findings = check_node_visible_from_a_root(doc, states)

    assert findings == []


def test_a_graph_with_no_cycle_hides_nobody(tmp_path):
    doc = _tree_with_register(tmp_path, [("D49", "D47"), ("D47", "NONE")])
    states = {"D49": ClosureClass.OPEN, "D47": ClosureClass.OPEN}

    assert check_node_visible_from_a_root(doc, states) == []


# --------------------------------------------------------------------------
# the vocabulary that made seven nodes vanish
# --------------------------------------------------------------------------


def test_blocked_needs_design_is_an_open_state_not_an_unknown_one():
    assert classify_state("BLOCCATO-SERVE-DESIGN") is ClosureClass.OPEN


def test_a_parent_closed_over_a_blocked_child_is_rejected(tmp_path):
    """D48 closed above an open D03b -- Ale's original observation."""
    doc = _tree_with_register(tmp_path, [("D48", "D03")])
    states = {"D48": ClosureClass.CLOSED, "D03B": ClosureClass.OPEN}

    findings = check_closed_over_open_child(doc, states)

    assert [f.rule for f in findings] == ["closed-over-open-child"]
    assert "D03B" in findings[0].what


@pytest.mark.parametrize("child_id", ["D03a", "D03A", "D03b", "D03B"])
def test_a_split_child_resolves_whatever_the_case_of_its_suffix(tmp_path, child_id):
    doc = _tree_with_register(tmp_path, [("D48", "D03")])
    states = {"D48": ClosureClass.CLOSED, child_id: ClosureClass.OPEN}

    findings = check_closed_over_open_child(doc, states)

    assert len(findings) == 1, f"{child_id} did not resolve as a sub-slice of D03"


# --------------------------------------------------------------------------
# the view itself -- the surface on which D27 was actually missing
# --------------------------------------------------------------------------


def test_the_rendered_board_shows_a_node_whose_cell_says_none(tmp_path):
    """End-to-end on the surface that hid it: D27 must appear in the board.

    The gate deciding correctly is not the deliverable -- the operator reads
    the BOARD. This pins the property on the rendered text.
    """
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    from mikado_board import build, read_edges, render

    _tree_with_register(
        tmp_path,
        [
            ("D27", "NONE — è **prerequisito** di D44 e di D20-lato-B"),
            ("D44", "**D27**"),
        ],
    )
    states = {"D27": ("BLOCCATO-SERVE-DESIGN", "derivazione"), "D44": ("PRONTO", "x")}

    deps, roots = build(states, read_edges(tmp_path / REGISTER))
    rendered = render(states, deps, roots)

    # Visibility is the property under test. Whether D27 shows as a root or as
    # D44's child depends on D44's own cell; what must never happen again is
    # the pair closing a cycle and dropping out of the render entirely.
    assert "D27" in rendered, "the node its own cell declares dependency-free is hidden"
    assert "D44" in rendered
    assert roots, "a graph whose every node is waited-for renders nothing at all"


def test_a_closure_over_an_undecidable_cell_is_unverifiable_not_a_rejection(
    tmp_path,
):
    doc = _tree_with_register(tmp_path, [("D17", "NONE (beneficia di D03)")])
    states = {"D17": ClosureClass.CLOSED, "D03B": ClosureClass.OPEN}

    findings = check_closed_over_open_child(doc, states)

    assert [f.severity for f in findings] == [Severity.UNVERIFIABLE]
    assert findings[0].rule == "closure-prerequisites-undecidable"
