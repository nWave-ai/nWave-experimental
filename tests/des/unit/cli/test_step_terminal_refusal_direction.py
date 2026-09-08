"""The ORCHESTRATOR line is derived from primitive rows, and only from them.

ADR-DES-003 G5: `ORCHESTRATOR` derives from the outcome, `TURNS-BOUGHT`, the
presence of `DIAGNOSTIC` and the pointable rows printed. A step passes NO prose:
the sentence a step cannot write is a sentence that cannot lie.

Three defects were measured into this shape, each a case below.

FIRST, six steps carried a constant naming `BLOCKED-BY` and the `DIAGNOSTIC`
whatever they printed, so a software refusal told its reader to read rows that
were not there. SECOND, the repair read "did a role run" off the diagnostic, and
a Product Owner whose envelope the boundary refuses leaves no diagnostic while
its process runs and its turn is paid -- the terminal said the software had
refused before buying one, over a turn that was bought. THIRD, §3 of the design
found the same class alive on the success side, in seven hand-written sentences
one of which promised `ORACLE-RED` on a branch that prints none.

So no step authors the line at all, and the rows it may name are asserted here
directly. `des integrate` and `des project` are included because they buy no
turn: their refusals can never point at a role's answer.
"""

from __future__ import annotations

import importlib

import pytest

from des.cli.step_terminal import orchestrator_line


#: Every row a derived sentence may point at.
ROWS = ("BLOCKED-BY", "DEFECT-OWNER", "DIAGNOSTIC")

#: Every command that prints a step terminal. None may author a sentence.
STEP_MODULES = (
    "des.cli.state",
    "des.cli.project",
    "des.cli.po",
    "des.cli.design",
    "des.cli.oracle",
    "des.cli.craft",
    "des.cli.verify",
    "des.cli.integrate",
    "des.cli.devops",
)


def test_a_step_that_bought_no_turn_is_told_the_how_is_the_whole_move() -> None:
    line = orchestrator_line(["DELIVERY-OUTCOME: Refusal", "TURNS-BOUGHT: 0"])
    assert "no role turn ran" in line
    for row in ROWS:
        assert row not in line


def test_a_bought_turn_whose_words_did_not_survive_names_the_role_and_the_cost() -> (
    None
):
    """The measured incident: not free, and nothing of the role's to read."""
    line = orchestrator_line(
        [
            "DELIVERY-OUTCOME: Indeterminate",
            "TURNS-BOUGHT: 1",
            "ROLE: nw-product-owner",
        ]
    )
    assert "nw-product-owner" in line
    assert "no role turn ran" not in line
    assert "the turn is spent" in line
    assert "DIAGNOSTIC" in line  # it names the row it is telling you is absent


@pytest.mark.parametrize("label", ["BLOCKED-BY", "DEFECT-OWNER"])
def test_a_carried_row_is_named_and_the_absent_one_is_not(label: str) -> None:
    line = orchestrator_line(
        [
            "DELIVERY-OUTCOME: Refusal",
            f"{label}: oracle",
            "TURNS-BOUGHT: 1",
            "ROLE: nw-software-crafter",
            'DIAGNOSTIC: "something"',
        ]
    )
    assert f"read {label} and the DIAGNOSTIC below" in line
    absent = "DEFECT-OWNER" if label == "BLOCKED-BY" else "BLOCKED-BY"
    assert absent not in line
    assert "nw-software-crafter" in line


def test_both_carried_rows_are_named_in_one_line() -> None:
    line = orchestrator_line(
        [
            "DELIVERY-OUTCOME: Refusal",
            "BLOCKED-BY: oracle",
            "DEFECT-OWNER: design",
            "TURNS-BOUGHT: 2",
            "ROLE: nw-acceptance-designer-reviewer",
            'DIAGNOSTIC: "something"',
        ]
    )
    assert "BLOCKED-BY and DEFECT-OWNER and the DIAGNOSTIC" in line


@pytest.mark.parametrize("module", STEP_MODULES)
def test_no_step_module_authors_a_sentence_about_the_block(module: str) -> None:
    """G5 made structural: a step has no direction to hand over at all.

    The seven `DIRECTION` dictionaries and the `role_move` parameter are gone.
    Asserting their absence is what stops the first defect returning under a new
    name, because a pointer written upstream cannot be removed downstream.
    """
    loaded = importlib.import_module(module)
    assert not hasattr(loaded, "DIRECTION"), module
    source = __import__("pathlib").Path(loaded.__file__).read_text(encoding="utf-8")
    assert "role_move" not in source, module
    for row in ROWS:
        # A row name may appear in a NEXT gloss or a HOW, never in a sentence a
        # step writes about the block: those are derived now.
        assert f"read {row}" not in source, (module, row)


def test_the_step_outcome_carries_the_rows_the_line_is_derived_from() -> None:
    """The facts travel, and both default to the honest side.

    A step that forgot to forward them reports no turn bought and no role, which
    understates the spend rather than claiming one that never happened.
    """
    from des.application.delivery_continuation import Disposition
    from des.application.delivery_steps import StepOutcome

    empty = StepOutcome(Disposition.Success)
    assert empty.turns_bought == 0
    assert empty.role is None
    carried = StepOutcome(Disposition.Refusal, turns_bought=2, role="nw-product-owner")
    assert (carried.turns_bought, carried.role) == (2, "nw-product-owner")
