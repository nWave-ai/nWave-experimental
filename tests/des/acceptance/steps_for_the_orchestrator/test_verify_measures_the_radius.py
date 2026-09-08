"""`des verify` measures the candidate's radius and hands it to both judges.

ADR-DES-003 §6: two things are never skipped -- an oracle exists before the
code, and a blind examiner judges the result without seeing it -- and how WIDE
that oracle and that examination must be is «not declared up front and not
promised by the Request: it is measured from what the candidate actually
touched».

The measure already exists (`measure_blast_radius`) and had one caller, its own
CLI. It enters the algebra at `verify`, after the candidate is built and before
the reviewer is bought: printed as a primitive `RADIUS:` row, and handed to the
whole-diff reviewer and to the examiner as DATA beside the admitted
observations. The software refuses NOTHING on it -- width is the reviewer's and
the examiner's judgement over a measured fact.

With the pre-craft oracle judge retired (§5), the whole-diff reviewer is the
oracle's only independent judge, so a finding «the oracle does not cover surface
X» comes back as `DEFECT-OWNER: oracle` and `NEXT` names the author's step. That
is the fork §6 describes and G7 signals by cardinality.
"""

from __future__ import annotations

from pathlib import Path

from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    accepted_values,
    block,
    nexts,
)


REQUEST = "one Request whose candidate radius is measured and handed to its judges"
ORACLE = "tests/acceptance/test_value.py"
SUPPORT = "tests/acceptance/support.py"
TARGET = "product_value.py"
RED_ORACLE = (
    "import pathlib\nimport sys\n\n\ndef test_value():\n"
    "    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))\n"
    "    from product_value import VALUE\n\n    assert VALUE == 1\n"
)


def crafted(root: Path, step) -> None:
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
            "design",
            "--repo-root",
            str(root),
            "--value",
            "1",
            answers=[
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": "bound the typed facts",
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
            ],
        )[0]
        == 0
    )
    assert (
        step(
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
                }
            ],
        )[0]
        == 0
    )
    assert (
        step(
            "craft",
            "--repo-root",
            str(root),
            "--value",
            "1",
            answers=[
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": "implemented the value",
                    },
                    "writes": {TARGET: "VALUE = 1\n"},
                }
            ],
        )[0]
        == 0
    )


def accepted(diagnostic: str) -> dict:
    return {
        "structured_output": {
            "outcome": "accepted",
            "diagnostic": diagnostic,
            "defect_owner": None,
            "defect_value": None,
        }
    }


def test_the_radius_is_a_primitive_row_on_the_verify_terminal(root: Path, step) -> None:
    crafted(root, step)
    code, out, err = step(
        "verify",
        "--repo-root",
        str(root),
        answers=[
            accepted("the whole diff implements the observation"),
            {
                "structured_output": {
                    "outcome": "accepted",
                    "diagnostic": "the observation is in the evidence",
                }
            },
        ],
    )
    assert code == 0, out + err
    radius = block(out, err)["RADIUS"]
    assert "tier=" in radius
    assert "files=" in radius
    assert "boundary=" in radius
    assert "consumers=" in radius


def test_both_judges_are_handed_the_same_measured_facts(
    root: Path, step, turns: Path
) -> None:
    """Data, not a gate: the reviewer and the examiner judge width over it."""
    import json

    crafted(root, step)
    code, out, err = step(
        "verify",
        "--repo-root",
        str(root),
        answers=[
            accepted("the whole diff implements the observation"),
            {
                "structured_output": {
                    "outcome": "accepted",
                    "diagnostic": "the observation is in the evidence",
                }
            },
        ],
    )
    assert code == 0, out + err
    rows = json.loads(turns.read_text())
    reviewer = next(r for r in rows if r["agent"] == "nw-software-crafter-reviewer")
    examiner = next(r for r in rows if r["agent"] == "nw-user-examiner")
    for row in (reviewer, examiner):
        assert "radius" in row["prompt"], row["agent"]
        assert "tier" in row["prompt"], row["agent"]


def test_a_reviewer_charging_the_oracle_names_the_authors_step(
    root: Path, step
) -> None:
    """§6's own example, and the fork G7 signals by cardinality."""
    crafted(root, step)
    code, out, err = step(
        "verify",
        "--repo-root",
        str(root),
        answers=[
            {
                "structured_output": {
                    "outcome": "rejected",
                    "diagnostic": "the oracle does not cover the touched surface",
                    "defect_owner": "oracle",
                    "defect_value": None,
                }
            }
        ],
    )
    assert code == 1
    lines = block(out, err)
    assert lines["DEFECT-OWNER"] == "oracle"
    assert "RADIUS" in lines
    assert "does not cover" in lines["DIAGNOSTIC"]
    moves = " ".join(nexts(out))
    assert f"des oracle --repo-root {root} --value 1 --finding -" in moves
    assert len(nexts(out)) > 1
