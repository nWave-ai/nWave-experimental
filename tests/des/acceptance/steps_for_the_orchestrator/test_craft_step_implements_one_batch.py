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

import json
import sys
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
AUTHORITY = "docs/product/architecture/brief.md"


def design_facts(
    decisions: tuple[str, ...] = ("one opaque semantic decision",),
) -> dict:
    return {
        "structured_output": {
            "outcome": "accepted",
            "diagnostic": "bound the value to its typed design facts",
            "design_facts": {
                "targets": [{"path": TARGET, "decision": "CREATE_NEW"}],
                "paradigm": "object_oriented",
                "decisions": list(decisions),
                "oracle": ORACLE,
                "acceptance_supports": [SUPPORT],
                "verification": [[sys.executable, "-m", "pytest", ORACLE]],
                "oracle_verification_index": 0,
            },
        }
    }


def with_oracle(root: Path, step) -> None:
    """Decompose, bind and admit the oracle -- everything craft consumes."""
    assert (
        step(
            "po",
            "--project",
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
            "--project",
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


def accepted_craft(body: str) -> list[dict]:
    return [
        {
            "structured_output": {
                "outcome": "accepted",
                "diagnostic": "implemented the value behind its oracle",
            },
            "writes": {TARGET: body},
        }
    ]


def test_a_design_correction_that_changes_the_facts_reopens_the_recorded_craft(
    root: Path, step, turns: Path
) -> None:
    """A craft record keyed on bytes alone outlived the design it implemented.

    Measured on a Node subject, 2026-09-15: the whole-diff review rejected a
    candidate for a defect in one bound decision, and `des design --finding -`
    rebound that decision. The production bytes had not moved, so `des craft`
    answered RECORDED and bought nothing, `des verify` could only fail on the
    corrected vector, and `des integrate` refused the superseded evidence. No
    step could hand the corrected decision to the crafter. The oracle keeps its
    record: it has its own correction, `des oracle --finding -`, and craft has
    none.
    """
    with_oracle(root, step)
    assert (
        step(
            "craft",
            "--repo-root",
            str(root),
            "--value",
            "1",
            answers=accepted_craft("VALUE = 1\n"),
        )[0]
        == 0
    )
    code, out, err = step(
        "design",
        "--repo-root",
        str(root),
        "--value",
        "1",
        "--finding",
        "-",
        answers=[
            design_facts(
                decisions=("one opaque semantic decision", "a corrected decision")
            )
        ],
        stdin="one bound decision is wrong for the installed shape",
    )
    assert code == 0, out + err
    assert "UNCHANGED" not in block(out, err)
    spent = len(asked(turns))

    code, out, err = step(
        "craft",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=accepted_craft("VALUE = 2\n"),
    )

    assert code == 0, out + err
    assert "RECORDED" not in block(out, err)
    assert asked(turns)[spent:] == ["nw-software-crafter"]
    assert (root / TARGET).read_text() == "VALUE = 2\n"
    assert any(ref.endswith("/craft") for ref in turn_refs(root))


def test_a_design_correction_repeating_the_facts_keeps_the_recorded_craft(
    root: Path, step, turns: Path
) -> None:
    """Only a CHANGED design reopens craft; an identical answer is a measured fact."""
    with_oracle(root, step)
    assert (
        step(
            "craft",
            "--repo-root",
            str(root),
            "--value",
            "1",
            answers=accepted_craft("VALUE = 1\n"),
        )[0]
        == 0
    )
    code, out, err = step(
        "design",
        "--repo-root",
        str(root),
        "--value",
        "1",
        "--finding",
        "-",
        answers=[design_facts()],
        stdin="a finding the architect answers by repeating itself",
    )
    assert code == 0, out + err
    assert "UNCHANGED" in block(out, err)
    spent = len(asked(turns))

    code, out, err = step(
        "craft",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=accepted_craft("VALUE = 2\n"),
    )

    assert code == 0, out + err
    assert "RECORDED" in block(out, err)
    assert len(asked(turns)) == spent
    assert (root / TARGET).read_text() == "VALUE = 1\n"


def design_manifest(
    decisions: tuple[str, ...] = ("one opaque semantic decision",),
) -> str:
    """The closed v1 manifest `des design --input -` binds without a turn."""
    return json.dumps(
        {
            "schema_version": 1,
            "authority": {"heading": "Value implemented behind its oracle"},
            "purpose": "Implement the value behind its own oracle.",
            "constraints": ["Keep the oracle immutable."],
            "targets": [
                {
                    "path": TARGET,
                    "decision": "CREATE_NEW",
                    "reason": "No module owns the value yet.",
                }
            ],
            "paradigm": "object_oriented",
            "decisions": list(decisions),
            "reuse_analysis": {"candidates": []},
            "prefactoring": {
                "applicability": "not_applicable",
                "reason": "The target is new.",
            },
            "agreement_analysis": {
                "applicability": "not_applicable",
                "reason": "No shared schema is touched.",
            },
            "boundaries": {
                "applicability": "not_applicable",
                "reason": "No port or dependency boundary changes.",
            },
            "public_oracle": {
                "observation": "The value module imports.",
                "stimulus": "Run the acceptance oracle.",
                "expected": "The oracle passes.",
                "falsifier": "Any import failure.",
            },
            "oracle": ORACLE,
            "acceptance_supports": [SUPPORT],
            "verification": [[sys.executable, "-m", "pytest", ORACLE]],
            "oracle_verification_index": 0,
        }
    )


def crafted_through_the_design_constructor(root: Path, step) -> None:
    """Bind through `--input -`, admit the oracle, and record one craft turn."""
    assert (
        step(
            "po",
            "--project",
            "--repo-root",
            str(root),
            answers=[accepted_values("A")],
            stdin=REQUEST,
        )[0]
        == 0
    )
    code, out, err = step(
        "design",
        "--repo-root",
        str(root),
        "--value",
        "1",
        "--input",
        "-",
        stdin=design_manifest(),
    )
    assert code == 0, out + err
    # `--replace-current` rewrites only a TRACKED authority, as a live checkout
    # carries it once the first binding is committed.
    git(root, "add", AUTHORITY)
    git(root, "commit", "-qm", "bound DESIGN authority")
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
    code, out, err = step(
        "craft",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=accepted_craft("VALUE = 1\n"),
    )
    assert code == 0, out + err
    assert any(ref.endswith("/craft") for ref in turn_refs(root))


def rebind_through_the_design_constructor(
    root: Path, step, decisions: tuple[str, ...]
) -> None:
    code, out, err = step(
        "design",
        "--repo-root",
        str(root),
        "--value",
        "1",
        "--replace-current",
        "--input",
        "-",
        stdin=design_manifest(decisions=decisions),
    )
    assert code == 0, out + err


def test_a_constructor_rebind_that_changes_the_facts_reopens_the_recorded_craft(
    root: Path, step, turns: Path
) -> None:
    """The closed-manifest rebind is a design correction too.

    Measured on a Node subject, 2026-09-16: `des design --replace-current
    --input -` rebound changed facts, the craft record survived, and `des craft`
    answered RECORDED, so the corrected decision never reached the crafter. The
    architect-turn correction already reopened craft; this constructor did not.
    """
    crafted_through_the_design_constructor(root, step)
    rebind_through_the_design_constructor(
        root, step, ("one opaque semantic decision", "a corrected decision")
    )
    spent = len(asked(turns))

    code, out, err = step(
        "craft",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=accepted_craft("VALUE = 2\n"),
    )

    assert code == 0, out + err
    assert "RECORDED" not in block(out, err)
    assert asked(turns)[spent:] == ["nw-software-crafter"]
    assert (root / TARGET).read_text() == "VALUE = 2\n"
    assert any(ref.endswith("/craft") for ref in turn_refs(root))


def test_a_constructor_rebind_repeating_the_facts_keeps_the_recorded_craft(
    root: Path, step, turns: Path
) -> None:
    """Only CHANGED constructor facts reopen craft; identical ones stay RECORDED."""
    crafted_through_the_design_constructor(root, step)
    rebind_through_the_design_constructor(root, step, ("one opaque semantic decision",))
    spent = len(asked(turns))

    code, out, err = step(
        "craft",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=accepted_craft("VALUE = 2\n"),
    )

    assert code == 0, out + err
    assert "RECORDED" in block(out, err)
    assert len(asked(turns)) == spent
    assert (root / TARGET).read_text() == "VALUE = 1\n"
