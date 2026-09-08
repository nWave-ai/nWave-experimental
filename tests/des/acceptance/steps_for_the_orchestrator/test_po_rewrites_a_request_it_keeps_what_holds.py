"""`des po` with a different Request REWRITES: it keeps what holds, archives the rest.

ADR-DES-003 §7. People change their mind halfway, and the DES had no move for
it: the only repair was deleting the state file by hand, which the orchestrator
did SIX times in two days. Each deletion also dropped every turn record, because
persisting a brand-new graph released the WHOLE turn namespace -- so a rewrite
cost the design, oracle and craft turns of every value, kept or not.

WHO DECIDES WHAT, and the line is the whole point. Which values still hold is a
SEMANTIC decision and stays with the Product Owner. The software then splits by
BYTE IDENTITY of the observation -- a primitive it can measure -- and never by
similarity, which it cannot: «the software never guesses a match».

NOTHING IS DELETED SILENTLY. Both lists are printed as rows, the archived bytes
are a readable Git ref, and where something was archived a second `NEXT` offers
the objection, so the orchestrator can correct the split with one more turn.
That second line is a real fork under G7.

ENACTMENT ORDER IS A LAW. Compare-and-swap first, drops last, so an
interruption leaves either the old graph whole or the new graph whole -- never a
graph without its records.
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    accepted_values,
    asked,
    block,
    git,
    nexts,
    observation,
)


FIRST = "the first Request, decomposed into two ordered values"
SECOND = "the second Request, which keeps one value and drops the other"
HANDOVER = Path(".nwave") / "des" / "handover.json"
ORACLE = "tests/acceptance/test_value.py"
SUPPORT = "tests/acceptance/support.py"
TARGET = "product_value.py"


def rewrite(*labels: str) -> dict:
    return {
        "structured_output": {
            "outcome": "accepted",
            "diagnostic": "one value still holds; the other does not",
            "values": [{"observation": observation(label)} for label in labels],
        }
    }


def design_facts() -> dict:
    return {
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


def stored(root: Path) -> dict:
    return json.loads((root / HANDOVER).read_text())


def turn_refs(root: Path) -> list[str]:
    listed = git(root, "for-each-ref", "--format=%(refname)", "refs/nwave/turns")
    return [line for line in listed.splitlines() if line]


def two_values_one_bound(root: Path, step) -> None:
    assert (
        step(
            "po",
            "--repo-root",
            str(root),
            answers=[accepted_values("A", "B")],
            stdin=FIRST,
        )[0]
        == 0
    )
    assert (
        step(
            "design", "--repo-root", str(root), "--value", "1", answers=[design_facts()]
        )[0]
        == 0
    )


def test_a_different_request_keeps_what_still_holds_and_archives_the_rest(
    root: Path, step, turns: Path
) -> None:
    two_values_one_bound(root, step)
    bound = stored(root)["values"][0]["authority"]
    spent = len(asked(turns))

    code, out, err = step(
        "po",
        "--repo-root",
        str(root),
        answers=[rewrite("A", "C")],
        stdin=SECOND,
    )

    assert code == 0, out + err
    lines = block(out, err)
    assert lines["TURNS-BOUGHT"] == "1"
    assert len(asked(turns)) == spent + 1
    # The split is SHOWN, all three sets, so it can be corrected.
    assert "KEPT" in lines
    assert "ARCHIVED" in lines
    assert "NEW" in lines
    assert observation("B") in out + err
    # The kept value keeps its authority: byte identity of the observation.
    graph = stored(root)
    assert graph["request"] == SECOND
    assert [value["observation"] for value in graph["values"]] == [
        observation("A"),
        observation("C"),
    ]
    assert graph["values"][0]["authority"] == bound


def test_the_archive_is_a_readable_ref_and_nothing_is_deleted_silently(
    root: Path, step
) -> None:
    two_values_one_bound(root, step)
    before = (root / HANDOVER).read_text()

    code, out, err = step(
        "po", "--repo-root", str(root), answers=[rewrite("A", "C")], stdin=SECOND
    )

    assert code == 0, out + err
    archive = block(out, err)["ARCHIVE"]
    assert archive.startswith("refs/nwave/archive/")
    # The old graph is READABLE at that ref, byte for byte.
    assert git(root, "cat-file", "-p", f"{archive}:handover.json") == before.rstrip(
        "\n"
    )


def test_a_kept_value_keeps_its_turn_records_under_the_new_request(
    root: Path, step
) -> None:
    """Re-keyed, not orphaned: the refs are keyed by the Request's digest."""
    two_values_one_bound(root, step)
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
                    "writes": {
                        ORACLE: "def test_value():\n    import product_value  # noqa\n",
                        SUPPORT: "MARKER = 1\n",
                    },
                }
            ],
        )[0]
        == 0
    )
    before = turn_refs(root)
    assert any(ref.endswith("/oracle") for ref in before), before

    assert (
        step("po", "--repo-root", str(root), answers=[rewrite("A", "C")], stdin=SECOND)[
            0
        ]
        == 0
    )

    after = turn_refs(root)
    assert any(ref.endswith("/oracle") for ref in after), after
    # Re-keyed onto the new digest, so the old key is gone and the record is not.
    assert set(after).isdisjoint(before)
    _code, out, err = step("state", "--repo-root", str(root))
    assert "oracle=recorded" in (out + err)


def test_an_archived_value_offers_the_objection_as_a_second_next(
    root: Path, step
) -> None:
    """A real fork under G7: the orchestrator may send the split back."""
    two_values_one_bound(root, step)
    code, out, err = step(
        "po", "--repo-root", str(root), answers=[rewrite("A", "C")], stdin=SECOND
    )
    assert code == 0, out + err
    moves = nexts(out)
    assert len(moves) > 1
    assert any("des po" in move and "--finding -" in move for move in moves)


def test_the_same_new_request_twice_is_a_resume(root: Path, step, turns: Path) -> None:
    """L1 over the rewrite: the second call is free."""
    two_values_one_bound(root, step)
    assert (
        step("po", "--repo-root", str(root), answers=[rewrite("A", "C")], stdin=SECOND)[
            0
        ]
        == 0
    )
    spent = len(asked(turns))
    graph = stored(root)

    code, out, err = step(
        "po", "--repo-root", str(root), answers=[rewrite("A", "C")], stdin=SECOND
    )

    assert code == 0, out + err
    assert len(asked(turns)) == spent
    assert stored(root) == graph
