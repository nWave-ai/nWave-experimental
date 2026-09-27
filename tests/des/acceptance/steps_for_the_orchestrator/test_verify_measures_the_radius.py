"""`des verify` measures the candidate's radius for explicit role inputs.

ADR-DES-003 §6: two things are never skipped -- an oracle exists before the
code, and a blind examiner judges the result without seeing it -- and how WIDE
that oracle and that examination must be is «not declared up front and not
promised by the Request: it is measured from what the candidate actually
touched».

The measure already exists (`measure_blast_radius`) and had one caller, its own
CLI. It enters the algebra at `verify`, after the candidate is built: printed
as a primitive `RADIUS:` row, then copied into reviewer and examiner artifacts
only when the host explicitly calls `prepare-role`. The software refuses
nothing on it and routes no finding; width remains an observation for a chosen
reviewer or examiner to assess.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from des.domain.public_observations import WITHHELD
from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    accepted_values,
    asked,
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
                            "verification": [[sys.executable, "-m", "pytest", ORACLE]],
                            "oracle_verification_index": 0,
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


def _prepare(root: Path, step, role: str, candidate: str) -> Path:
    code, out, err = step(
        "prepare-role",
        "--repo-root",
        str(root),
        "--role",
        role,
        "--candidate",
        candidate,
    )
    assert code == 0, out + err
    return root / block(out, err)["INPUT"]


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


def test_reviewer_receives_measured_radius_while_examiner_stays_source_blind(
    root: Path, step, turns: Path
) -> None:
    """The host separately selects full review and source-blind EXAMINE inputs."""

    crafted(root, step)
    spent = len(asked(turns))
    code, out, err = step(
        "verify",
        "--repo-root",
        str(root),
        answers=[],
    )
    assert code == 0, out + err
    candidate = block(out, err)["CANDIDATE"]
    reviewer = json.loads(_prepare(root, step, "reviewer", candidate).read_bytes())
    examiner = json.loads(_prepare(root, step, "examiner", candidate).read_bytes())
    assert asked(turns)[spent:] == []
    assert "tier=" in reviewer["radius"]
    assert examiner["radius"] == WITHHELD


def test_a_host_recorded_reviewer_finding_is_typed_without_auto_routing(
    root: Path, step
) -> None:
    """§6's own example, and the fork G7 signals by cardinality."""
    crafted(root, step)
    code, out, err = step("verify", "--repo-root", str(root), answers=[])
    assert code == 0, out + err
    candidate = block(out, err)["CANDIDATE"]
    _prepare(root, step, "reviewer", candidate)
    code, recorded_out, recorded_err = step(
        "record-role-result",
        "--repo-root",
        str(root),
        "--role",
        "reviewer",
        "--candidate",
        candidate,
        "--provider",
        "claude",
        "--model",
        "host-observation-model",
        "--session-id",
        "radius-reviewer-finding",
        "--input",
        "-",
        stdin=json.dumps(
            {
                "structured_output": {
                    "outcome": "rejected",
                    "diagnostic": "the oracle does not cover the touched surface",
                    "defect_owner": "oracle",
                    "defect_value": None,
                }
            }
        ),
    )
    assert code == 0, recorded_out + recorded_err
    result = root / block(recorded_out, recorded_err)["RESULT"]
    observed = json.loads(result.read_bytes())
    assert observed["result"]["defect_owner"] == "oracle"
    assert (
        observed["result"]["diagnostic"]
        == "the oracle does not cover the touched surface"
    )
    assert all("des oracle" not in move for move in nexts(recorded_out))
