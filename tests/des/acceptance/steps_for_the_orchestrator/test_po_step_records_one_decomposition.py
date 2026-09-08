"""Public oracle: `des po`, one Product Owner turn invoked alone.

ADR-SSOT-002 Section 4b names this step by PROPERTY -- «Recording an accepted
decomposition as owned state: takes the validated ordered observations, returns
the persisted graph, or the drift that prevented the write.»

The measured defect it closes is stated in the same section.  In run
`20260905T062139Z-38400` the Product Owner answered `rejected` carrying a
complete and correct three-value decomposition in its diagnostic, and the runner
discarded all three and refused the whole Request, because a step that also
owned the sequence had to turn a role's LOCAL outcome into a verdict about the
Request.  Invoked alone the step reports what the role said and returns; the
orchestrator decides what it means.
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    accepted_values,
    asked,
    block,
    nexts,
    observation,
)


REQUEST = "one Request the Product Owner decomposes into its ordered values"
OTHER_REQUEST = "a different Request that must never overwrite the first"
HANDOVER = Path(".nwave") / "des" / "handover.json"


def test_an_accepted_turn_records_the_graph_and_names_the_next_step(
    root: Path, step, turns: Path
) -> None:
    code, out, err = step(
        "po",
        "--repo-root",
        str(root),
        answers=[accepted_values("A", "B")],
        stdin=REQUEST,
    )
    assert code == 0, out + err
    lines = block(out, err)
    assert lines["DELIVERY-OUTCOME"] == "Success"
    assert observation("A") in out
    assert observation("B") in out
    assert nexts(out) == [f"des design --repo-root {root} --value 1"]
    assert "decomposed into its ordered" in lines["DIAGNOSTIC"]
    stored = json.loads((root / HANDOVER).read_text())
    assert stored["request"] == REQUEST
    assert [value["observation"] for value in stored["values"]] == [
        observation("A"),
        observation("B"),
    ]
    assert asked(turns) == ["nw-product-owner"]


def test_a_rejecting_turn_forwards_the_role_diagnostic_and_runs_nothing_else(
    root: Path, step, turns: Path
) -> None:
    """The 06:21:39 defect: the role's meaning reaches the orchestrator intact."""
    finding = (
        "Request carries three independently shippable observable outcomes "
        "rather than one; ordered as walking skeleton, then the second, then "
        "the third"
    )
    code, out, err = step(
        "po",
        "--repo-root",
        str(root),
        answers=[
            {
                "structured_output": {
                    "outcome": "rejected",
                    "diagnostic": finding,
                    # The real boundary requires the field on every Product
                    # Owner envelope, so a fake omitting it would measure
                    # the schema rather than the law under test.
                    "values": [],
                }
            }
        ],
        stdin=REQUEST,
    )
    assert code == 1
    lines = block(out, err)
    assert lines["DELIVERY-OUTCOME"] == "Refusal"
    assert "three independently shippable" in lines["DIAGNOSTIC"]
    assert not (root / HANDOVER).exists()
    assert asked(turns) == ["nw-product-owner"]
    assert any(item.startswith("des po --repo-root") for item in nexts(out))


def test_the_same_request_twice_is_a_resume_and_never_a_second_paid_turn(
    root: Path, step, turns: Path
) -> None:
    """Section 4b: every step is idempotent against the two owned facts."""
    first = step(
        "po", "--repo-root", str(root), answers=[accepted_values("A")], stdin=REQUEST
    )
    assert first[0] == 0, first[1] + first[2]
    persisted = (root / HANDOVER).read_bytes()

    code, out, err = step(
        "po", "--repo-root", str(root), answers=[accepted_values("A")], stdin=REQUEST
    )

    assert code == 0, out + err
    assert block(out, err)["DELIVERY-OUTCOME"] == "Success"
    assert (root / HANDOVER).read_bytes() == persisted
    assert asked(turns) == ["nw-product-owner"]


def test_a_different_request_rewrites_instead_of_refusing(
    root: Path, step, turns: Path
) -> None:
    """ADR-DES-003 §7: a changed mind is a move, not a mismatch.

    `HandoverRequestMismatch` was the sequence refusal here, and the only repair
    it left was deleting the handover by hand -- done six times in two days,
    each deletion also dropping every turn record behind it. The step now runs
    the rewrite turn: the Product Owner says which values still hold, the
    software splits by byte identity, and both lists are printed so the split
    can be corrected. Nothing is deleted silently; the previous graph is a
    readable ref.
    """
    step("po", "--repo-root", str(root), answers=[accepted_values("A")], stdin=REQUEST)
    spent = len(asked(turns))

    code, out, err = step(
        "po",
        "--repo-root",
        str(root),
        answers=[
            {
                "structured_output": {
                    "outcome": "accepted",
                    "diagnostic": "the first value no longer holds",
                    "values": [{"observation": observation("B")}],
                }
            }
        ],
        stdin=OTHER_REQUEST,
    )

    assert code == 0, out + err
    lines = block(out, err)
    assert "ARCHIVED" in lines
    assert "NEW" in lines
    assert lines["ARCHIVE"].startswith("refs/nwave/archive/")
    assert len(asked(turns)) == spent + 1
    stored = json.loads((root / HANDOVER).read_text())
    assert stored["request"] == OTHER_REQUEST


def test_an_empty_request_is_refused_before_any_turn_is_bought(
    root: Path, step, turns: Path
) -> None:
    code, out, err = step("po", "--repo-root", str(root), answers=[], stdin="")
    assert code == 1
    assert block(out, err)["WHAT"] == "InvalidRequest"
    assert asked(turns) == []
