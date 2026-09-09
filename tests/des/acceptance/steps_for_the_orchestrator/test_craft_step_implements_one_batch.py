"""Public oracle: `des craft --value N`, one crafter turn invoked alone.

ADR-SSOT-002 Section 4b, Amendment 2026-09-06: a refusing craft turn names its
blocker in a closed word of its typed payload, and the COMPOSED run spends one
window on the role that word names.  A step invoked alone does the opposite half
of the same rule -- it returns the word as DATA and stops, because choosing
which role answers a finding is the orchestrator's decision.

The defect this closes is measured there too: in runs 31, 32b and 33 the
crafter found a case red for a defect of the ORACLE and refused, and the
runner's single `CraftRejected` answer sent the finding to a resume that
returned to the same crafter over the same oracle -- three runs and roughly $8
to buy what one $0.3 designer turn answers.
"""

from __future__ import annotations

from pathlib import Path

from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    accepted_values,
    asked,
    block,
    git,
    nexts,
)


REQUEST = "one Request whose single value is implemented behind its own oracle"
ORACLE = "tests/acceptance/test_value.py"
SUPPORT = "tests/acceptance/support.py"
TARGET = "src/product/value.py"
RED_ORACLE = "def test_value():\n    import product.value  # noqa\n"


def design_facts() -> dict:
    return {
        "structured_output": {
            "outcome": "accepted",
            "diagnostic": "bound the value to its typed design facts",
            "design_facts": {
                "targets": [{"path": TARGET, "decision": "CREATE_NEW"}],
                "paradigm": "object_oriented",
                "decisions": ["one opaque semantic decision"],
                "oracle": ORACLE,
                "acceptance_supports": [SUPPORT],
                "verification": [["python", "-m", "pytest", ORACLE]],
            },
        }
    }


def with_oracle(root: Path, step) -> None:
    """Decompose, bind and admit the oracle -- everything craft consumes."""
    assert (
        step(
            "po",
            "--repo-root",
            str(root),
            answers=[accepted_values("A")],
            stdin=REQUEST,
        )[0]
        == 0
    )
    assert (
        step(
            "design", "--repo-root", str(root), "--value", "1", answers=[design_facts()]
        )[0]
        == 0
    )
    code, out, err = step(
        "oracle",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[
            {
                "structured_output": {
                    "outcome": "accepted",
                    "diagnostic": "authored the oracle",
                },
                "writes": {ORACLE: RED_ORACLE, SUPPORT: "MARKER = 1\n"},
            },
            {
                "structured_output": {
                    "outcome": "accepted",
                    "diagnostic": "the oracle set is admissible",
                }
            },
        ],
    )
    assert code == 0, out + err


def turn_refs(root: Path) -> list[str]:
    listed = git(root, "for-each-ref", "--format=%(refname)", "refs/nwave/turns")
    return [line for line in listed.splitlines() if line]


def test_an_accepted_turn_writes_the_target_and_records_the_craft(
    root: Path, step, turns: Path
) -> None:
    with_oracle(root, step)
    code, out, err = step(
        "craft",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[
            {
                "structured_output": {
                    "outcome": "accepted",
                    "diagnostic": "implemented the value behind its oracle",
                },
                "writes": {TARGET: "VALUE = 1\n"},
            }
        ],
    )
    assert code == 0, out + err
    lines = block(out, err)
    assert lines["DELIVERY-OUTCOME"] == "Success"
    assert "implemented the value" in lines["DIAGNOSTIC"]
    assert (root / TARGET).read_text() == "VALUE = 1\n"
    assert asked(turns)[-1] == "nw-software-crafter"
    assert any(ref.endswith("/craft") for ref in turn_refs(root))
    assert nexts(out) == [f"des verify --repo-root {root}"]


def test_a_refusing_turn_returns_its_blocker_word_and_routes_to_nobody(
    root: Path, step, turns: Path
) -> None:
    """Runs 31/32b/33: the finding about the ORACLE must not return to the crafter."""
    with_oracle(root, step)
    spent = len(asked(turns))
    code, out, err = step(
        "craft",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[
            {
                "structured_output": {
                    "outcome": "rejected",
                    "diagnostic": (
                        "the failing line lives in the immutable oracle, which I "
                        "must not edit"
                    ),
                    "blocked_by": "oracle",
                }
            }
        ],
    )
    assert code == 1
    lines = block(out, err)
    assert lines["DELIVERY-OUTCOME"] == "Refusal"
    assert lines["WHAT"] == "CraftRejected"
    assert lines["BLOCKED-BY"] == "oracle"
    assert "immutable oracle" in lines["DIAGNOSTIC"]
    # ONE turn, and no second role: the window belongs to the orchestrator.
    assert len(asked(turns)) == spent + 1
    moves = " ".join(nexts(out))
    assert f"des oracle --repo-root {root} --value 1 --finding -" in moves
    assert f"des design --repo-root {root} --value 1 --finding -" in moves


def test_a_recorded_craft_turn_is_a_resume_and_buys_nothing(
    root: Path, step, turns: Path
) -> None:
    with_oracle(root, step)
    accepted = [
        {
            "structured_output": {
                "outcome": "accepted",
                "diagnostic": "implemented the value behind its oracle",
            },
            "writes": {TARGET: "VALUE = 1\n"},
        }
    ]
    assert (
        step("craft", "--repo-root", str(root), "--value", "1", answers=accepted)[0]
        == 0
    )
    spent = len(asked(turns))

    code, out, err = step(
        "craft", "--repo-root", str(root), "--value", "1", answers=accepted
    )

    assert code == 0, out + err
    assert len(asked(turns)) == spent


def test_crafting_before_the_oracle_is_recorded_succeeds(
    root: Path, step, turns: Path
) -> None:
    assert (
        step(
            "po",
            "--repo-root",
            str(root),
            answers=[accepted_values("A")],
            stdin=REQUEST,
        )[0]
        == 0
    )
    assert (
        step(
            "design", "--repo-root", str(root), "--value", "1", answers=[design_facts()]
        )[0]
        == 0
    )
    spent = len(asked(turns))
    code, out, err = step(
        "craft",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[
            {
                "structured_output": {
                    "outcome": "accepted",
                    "diagnostic": "implemented",
                },
                "writes": {TARGET: "VALUE = 1\n"},
            }
        ],
    )
    assert code == 0, out + err
    assert len(asked(turns)) == spent + 1
