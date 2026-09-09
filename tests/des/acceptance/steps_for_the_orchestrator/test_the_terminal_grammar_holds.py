"""The terminal block obeys the grammar of ADR-DES-003 §3, on every step.

§3 states the block a step prints IS the contract, and gives it laws the shared
renderer must make unrepresentable rather than a reviewer must catch. This file
is the executable half of G1, G3, G5, G6 and G7.

- **G1** one outcome first, one HOW-TO-INVOKE last, one stream.
- **G3** a terminal names only rows it carries. §3 records the surviving
  violation by reading the code: `oracle.py` `DIRECTION[True]` promises
  «ORACLE-RED is the evidence» while the RECORDED branch prints no such row.
- **G5** `ORCHESTRATOR` derives from primitive rows only and is ABSENT on
  `Success`, where the move available now IS `NEXT` (GDP-10).
- **G6** `TURNS-BOUGHT` and `ROLE` are primitive rows with named consumers: the
  orchestrator's cost judgement, and G5's own derivation.
- **G7** the fork is the COUNT of `NEXT` lines. A sequence refusal has one
  lawful move -- the producing step -- so it prints exactly one.
"""

from __future__ import annotations

from pathlib import Path

from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    accepted_values,
    block,
)


REQUEST = "one Request whose terminal grammar is read on every step"
ROWS = ("BLOCKED-BY", "DEFECT-OWNER", "DIAGNOSTIC", "ORACLE-RED", "RADIUS", "CANDIDATE")

BOUND = {
    "structured_output": {
        "outcome": "accepted",
        "diagnostic": "bound the typed facts",
        "design_facts": {
            "targets": [{"path": "product_value.py", "decision": "CREATE_NEW"}],
            "paradigm": "object_oriented",
            "decisions": ["one opaque semantic decision"],
            "oracle": "tests/acceptance/test_value.py",
            "acceptance_supports": ["tests/acceptance/support.py"],
            "verification": [
                ["python", "-m", "pytest", "tests/acceptance/test_value.py"]
            ],
        },
    }
}


#: Written BEFORE the work and on stderr, so it is not a row of the block: the
#: runtime declaration migrated from the retired composed run (census rows 1-5,
#: `test_a_step_declares_the_tree_it_runs.py`). G1 governs the TERMINAL, and a
#: line printed before a step has an outcome to state cannot be one of its rows
#: -- reading it as one would make «the outcome is first» false for a fact the
#: grammar never claimed to order. That it PRECEDES the block is the whole point
#: of it, and is asserted below.
PRE_WORK = ("DELIVERY-RUNTIME: ",)


def lines_of(out: str, err: str) -> list[str]:
    return [
        line
        for line in (out + "\n" + err).splitlines()
        if line.strip() and not line.startswith(PRE_WORK)
    ]


def labels(out: str, err: str) -> set[str]:
    return {
        line.split(": ", 1)[0]
        for line in lines_of(out, err)
        if ": " in line and line.split(": ", 1)[0].isupper()
    }


def nexts(out: str, err: str) -> list[str]:
    return [line for line in lines_of(out, err) if line.startswith("NEXT: ")]


def decomposed(root: Path, step) -> None:
    assert (
        step(
            "po",
            "--repo-root",
            str(root),
            answers=[accepted_values("A", "B")],
            stdin=REQUEST,
        )[0]
        == 0
    )


def test_g1_one_outcome_first_and_one_recall_last(root: Path, step) -> None:
    decomposed(root, step)
    for argv in (
        ("state", "--repo-root", str(root)),
        ("design", "--repo-root", str(root), "--value", "9"),
        ("craft", "--repo-root", str(root), "--value", "1"),
    ):
        _code, out, err = step(*argv)
        printed = lines_of(out, err)
        outcomes = [
            i for i, line in enumerate(printed) if line.startswith("DELIVERY-OUTCOME: ")
        ]
        recalls = [
            i for i, line in enumerate(printed) if line.startswith("HOW-TO-INVOKE: ")
        ]
        assert outcomes == [0], (argv, printed[:3])
        assert recalls == [len(printed) - 1], (argv, printed[-3:])
        # And the one line the block excludes is excluded because it comes
        # FIRST, before the step had an outcome to state.
        if argv[0] != "state":
            everything = [x for x in (err + "\n" + out).splitlines() if x.strip()]
            assert everything[0].startswith(PRE_WORK), everything[:3]


def test_g5_no_orchestrator_line_on_success(root: Path, step) -> None:
    """On Success the move available now IS `NEXT`; a second sentence is waste."""
    decomposed(root, step)
    for argv in (
        ("state", "--repo-root", str(root)),
        ("po", "--repo-root", str(root)),
    ):
        code, out, err = step(*argv, answers=[accepted_values("A", "B")], stdin=REQUEST)
        assert code == 0, (argv, out + err)
        assert "ORCHESTRATOR" not in labels(out, err), argv


def test_g6_every_step_prints_the_turns_it_bought(root: Path, step) -> None:
    """The count is a primitive row, not two English sentences chosen from it."""
    code, out, err = step(
        "po",
        "--repo-root",
        str(root),
        answers=[accepted_values("A")],
        stdin=REQUEST,
    )
    assert code == 0, out + err
    assert block(out, err)["TURNS-BOUGHT"] == "1"
    assert block(out, err)["ROLE"] == "nw-product-owner"

    _code, out, err = step("state", "--repo-root", str(root))
    assert block(out, err)["TURNS-BOUGHT"] == "0"
    assert "ROLE" not in labels(out, err)


def test_g6_a_bought_turn_whose_words_died_still_reports_its_cost(
    root: Path, step
) -> None:
    """The incident of §0: a paid turn reported as no turn at all."""
    code, out, err = step(
        "po",
        "--repo-root",
        str(root),
        answers=[
            {
                "structured_output": {
                    "outcome": "rejected",
                    "diagnostic": "an answer the runner will not parse",
                }
            }
        ],
        stdin=REQUEST,
    )
    assert code == 1
    assert block(out, err)["WHAT"] == "ModelEnvelopeUnavailable"
    assert block(out, err)["TURNS-BOUGHT"] == "1"
    assert block(out, err)["ROLE"] == "nw-product-owner"


def test_g7_a_sequence_refusal_prints_exactly_one_next(root: Path, step) -> None:
    """One lawful move -- the producing step -- so no fork is signalled."""
    decomposed(root, step)
    assert (
        step(
            "design",
            "--repo-root",
            str(root),
            "--value",
            "1",
            answers=[BOUND],
        )[0]
        == 0
    )
    for argv, what in (
        (("design", "--repo-root", str(root), "--value", "9"), "ValueOutOfRange"),
        (("oracle", "--repo-root", str(root), "--value", "2"), "DesignUnbound"),
    ):
        code, out, err = step(*argv)
        assert code == 1, argv
        assert block(out, err)["WHAT"] == what, argv
        assert len(nexts(out, err)) == 1, (argv, nexts(out, err))


def test_g3_no_line_names_a_row_the_block_does_not_carry(root: Path, step) -> None:
    """Read over the WHOLE block, not one branch of one line.

    §3 records the surviving violation: `oracle`'s success sentence promised
    ORACLE-RED on a branch that prints none. The law holds over every printed
    line, whatever the outcome.
    """
    decomposed(root, step)
    for argv in (
        ("state", "--repo-root", str(root)),
        ("design", "--repo-root", str(root), "--value", "9"),
        ("craft", "--repo-root", str(root), "--value", "1"),
        ("verify", "--repo-root", str(root)),
    ):
        _code, out, err = step(*argv)
        carried = labels(out, err)
        for line in lines_of(out, err):
            label, _, text = line.partition(": ")
            if label in ("NEXT", "HOW-TO-INVOKE"):
                continue
            for row in ROWS:
                assert row not in text or row in carried, (argv, line)
