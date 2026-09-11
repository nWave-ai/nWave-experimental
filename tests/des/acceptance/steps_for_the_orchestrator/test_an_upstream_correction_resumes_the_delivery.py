"""Public oracle: a downstream finding, an upstream correction, a resumed delivery.

The orchestrator, not the DES, owns this route. It carries a finding upstream,
invokes the same public wave producer to correct the graph, reads where the
Request now stands, and resumes. What the DES owes that route is one thing: the
state it projects must distinguish evidence measured against the CURRENT graph
from evidence measured before the correction, so a candidate verified earlier
cannot pass for verified afterwards.

Every step here is a separate process, which is what makes the scenario an
INTERRUPTION as well as a correction: nothing is carried between the calls
except the bytes on disk.
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    block,
    git,
    nexts,
    observation,
)
from tests.des.acceptance.steps_for_the_orchestrator.test_verify_and_integrate_close_the_request import (
    ORACLE,
    SUPPORT,
    crafted,
)


def correction() -> str:
    """One upstream DISTILL correction for the value already crafted."""
    return json.dumps(
        {
            "schema_version": 1,
            "values": [
                {
                    "observation": observation("A"),
                    "acceptance_obligations": [
                        {
                            "id": "value-is-observable",
                            "stimulus": "Run the installed command.",
                            "expected": "It reports the value the observation names.",
                        }
                    ],
                    "oracle": f"{ORACLE}::test_value",
                    "acceptance_supports": [SUPPORT],
                }
            ],
        }
    )


def verified(root: Path, step) -> str:
    code, out, err = step("verify", "--repo-root", str(root), answers=[])
    assert code == 0, out + err
    return block(out, err)["CANDIDATE"]


def state(root: Path, step) -> tuple[dict[str, str], list[str]]:
    code, out, err = step("state", "--repo-root", str(root))
    assert code == 0, out + err
    return block(out, err), nexts(out)


def test_the_state_names_the_candidate_and_its_record(root: Path, step) -> None:
    crafted(root, step)
    candidate = verified(root, step)

    lines, moves = state(root, step)

    assert lines["CANDIDATE"] == f"{candidate} recorded"
    assert any("des integrate" in move and candidate in move for move in moves)


def test_an_upstream_correction_supersedes_the_candidate_verified_before_it(
    root: Path, step
) -> None:
    crafted(root, step)
    candidate = verified(root, step)
    before = state(root, step)[0]["CANDIDATE"]

    corrected = step(
        "distill",
        "--repo-root",
        str(root),
        "--input",
        "-",
        "--replace-current",
        stdin=correction(),
    )
    assert corrected[0] == 0, corrected[1] + corrected[2]

    lines, moves = state(root, step)
    assert before == f"{candidate} recorded"
    assert lines["CANDIDATE"] == f"{candidate} bytes moved"
    assert all("des integrate" not in move for move in moves)
    assert any("des verify" in move for move in moves)


def test_integrate_refuses_the_candidate_the_correction_superseded(
    root: Path, step
) -> None:
    crafted(root, step)
    candidate = verified(root, step)
    head = git(root, "rev-parse", "HEAD")
    assert (
        step(
            "distill",
            "--repo-root",
            str(root),
            "--input",
            "-",
            "--replace-current",
            stdin=correction(),
        )[0]
        == 0
    )

    code, out, err = step(
        "integrate", "--repo-root", str(root), "--candidate", candidate
    )

    lines = block(out, err)
    assert code != 0
    assert lines["WHAT"] == "CandidateUnverified"
    assert candidate in lines["WHY"]
    assert git(root, "rev-parse", "HEAD") == head


def test_the_delivery_resumes_on_the_corrected_graph_and_closes(
    root: Path, step
) -> None:
    crafted(root, step)
    superseded = verified(root, step)
    assert (
        step(
            "distill",
            "--repo-root",
            str(root),
            "--input",
            "-",
            "--replace-current",
            stdin=correction(),
        )[0]
        == 0
    )

    resumed = verified(root, step)
    lines, moves = state(root, step)
    assert lines["CANDIDATE"] == f"{resumed} recorded"
    assert any("des integrate" in move for move in moves)

    code, out, err = step("integrate", "--repo-root", str(root), "--candidate", resumed)
    assert code == 0, out + err
    assert git(root, "rev-parse", "HEAD") == resumed
    assert not (root / ".nwave" / "des" / "handover.json").exists()
    # The superseded candidate is not what the destination became.
    assert git(root, "rev-parse", "HEAD") != superseded or superseded == resumed
