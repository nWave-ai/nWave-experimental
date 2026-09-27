"""A moved craft record is settled by its own green oracle -- or it is not.

THE OBSERVATION, stated as an operator sees it.  `des state` reports a value
whose craft record exists but whose recorded tree no longer matches the current
bytes of its mutable targets (`craft=bytes moved`), and names `des craft`.  When
that value's TRACKED oracle -- the one the graph already carries -- is executed
on those current bytes and observed GREEN, `des craft` reports the turn complete,
re-points the record at the bytes, buys NO crafter turn, names the following owed
step, and STATES that an observed-green oracle was the witness.  When the oracle
is red, broken or could not be executed, the crafter turn is bought exactly as it
is today; and when no craft record exists at all the turn is bought too, so a
green oracle can never complete a craft that was never recorded.

WHY THE FOURTH SCENARIO IS NOT DECORATION.  Path-existence-as-green is the
surrogate that skipped craft twice on 2026-09-04.  The record-first gate is the
whole difference between «this work was done and its bytes moved» and «these
bytes happen to satisfy an assertion», and only a scenario that hand-writes the
production bytes WITHOUT ever recording a craft turn can falsify it.

EVERYTHING HERE IS DRIVEN THROUGH THE PUBLIC STEP SURFACE and nothing else: one
real repository, the shared fake provider on `PATH`, and the real `des po`,
`des design`, `des oracle`, `des craft`, `des state` invocations an orchestrator
makes.  No runner method is imported, no internal record is written by hand, and
the turn LOG is what makes «no crafter turn was bought» a measurement rather
than a claim.

THE TWO FIXTURE ORACLES ARE CHOSEN SO THEIR VERDICT IS CONSTRUCTIBLE, not
assumed.  The settling one asserts the production module EXISTS: red before
craft, green after it, green again after the bytes move.  The refusing one
asserts the module's exact CONTENT: red before craft by an ASSERTION rather than
by an exception -- a module-level import of a file that does not exist yet would
score `broken` at authoring time and the oracle step would refuse before the
scenario began -- green after craft, red after the move.

Run it directly (`python <this file>`) or under pytest; both execute the same
observation and the exit status carries the verdict.
"""

from __future__ import annotations

import sys
from pathlib import Path


#: The repository root, so the standalone form resolves `tests.…` exactly as the
#: pytest form does.  The oracle is a script an examiner may run with no
#: knowledge of how the suite is invoked.
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest

from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    accepted_values,
    asked,
    block,
    git,
    nexts,
    observation,
)


#: One Request, decomposed into one value by the fake Product Owner.
REQUEST = "deliver the value module the operator reads\n"
LABEL = "alpha"
OBSERVATION = observation(LABEL)

#: The value's ONE production target and its TRACKED oracle.  The oracle sits
#: under the subject's default test paths, which is what makes it the acceptance
#: designer's own substrate; the target is the only mutable production path, so
#: the craft record is a statement about exactly these bytes.
TARGET = "src/product/value.py"
ORACLE = "tests/test_value_module.py"

#: What the crafter writes, and what the operator then MOVES.
CRAFTED = "VALUE = 1\n"
MOVED = "VALUE = 2\n"

#: GREEN after the move: the module still exists.  Red before craft.
EXISTENCE_ORACLE = (
    "from pathlib import Path\n"
    "\n"
    "\n"
    "def test_the_value_module_is_present():\n"
    f"    assert Path({TARGET!r}).exists()\n"
)

#: RED after the move: the module's bytes are no longer the crafted ones.  Red
#: before craft too, and by an ASSERTION -- never by an import of an absent
#: module, which would be collected as an ERROR and scored `broken`.
CONTENT_ORACLE = (
    "from pathlib import Path\n"
    "\n"
    "\n"
    "def test_the_value_module_holds_the_crafted_bytes():\n"
    f"    module = Path({TARGET!r})\n"
    f"    assert module.exists() and module.read_text() == {CRAFTED!r}\n"
)


def _design_answer() -> dict:
    """The architect's typed facts for this value, in the provider's own shape.

    The verification vector NAMES the oracle and leads with this interpreter,
    because the runner reuses the first declared vector containing the oracle
    path as an exact token for its own execution.  The admitted floor form
    (`python -m pytest …`) would score `broken` on a box carrying only
    `python3`, which would measure the fixture instead of the law.
    """
    return {
        "structured_output": {
            "outcome": "accepted",
            "diagnostic": "one production target behind one executable oracle",
            "design_facts": {
                "targets": [{"path": TARGET, "decision": "CREATE_NEW"}],
                "paradigm": "object_oriented",
                "decisions": [
                    "the value module is the one production path this value moves"
                ],
                "oracle": ORACLE,
                "acceptance_supports": [],
                "verification": [[sys.executable, "-m", "pytest", ORACLE, "-q"]],
                "oracle_verification_index": 0,
            },
        }
    }


def _oracle_answer(body: str) -> dict:
    """The acceptance designer's one turn: it writes the oracle and says so."""
    return {
        "writes": {ORACLE: body},
        "structured_output": {
            "outcome": "accepted",
            "diagnostic": "authored the candidate public oracle for this value",
        },
    }


def _craft_answer(content: str = CRAFTED) -> dict:
    """The crafter's one turn: it writes the production target and nothing else."""
    return {"writes": {TARGET: content}}


def _walk_to_a_recorded_craft(step, root: Path, oracle_body: str) -> None:
    """po -> design -> oracle -> craft, all through the real step surface.

    Every invocation is asserted to have succeeded, because a scenario that
    silently walked only half way would measure `des craft` in a state this
    observation says nothing about.
    """
    code, out, _ = step(
        "po",
        "--project",
        "--repo-root",
        str(root),
        stdin=REQUEST,
        answers=[accepted_values(LABEL)],
    )
    assert code == 0, out
    code, out, _ = step(
        "design",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[_design_answer()],
    )
    assert code == 0, out
    code, out, err = step(
        "oracle",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[_oracle_answer(oracle_body)],
    )
    assert code == 0, out + err
    code, out, err = step(
        "craft",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[_craft_answer()],
    )
    assert code == 0, out + err
    assert (root / TARGET).read_text() == CRAFTED


def test_a_green_tracked_oracle_settles_the_moved_record_and_buys_no_turn(
    root: Path, step, turns: Path
) -> None:
    """The whole observation, in one walk an orchestrator could reproduce."""
    _walk_to_a_recorded_craft(step, root, EXISTENCE_ORACLE)
    bought_before = asked(turns)

    # The operator moves the recorded bytes.  The tracked oracle still holds.
    (root / TARGET).write_text(MOVED)

    code, out, err = step("state", "--repo-root", str(root))
    assert code == 0, out
    assert "craft=bytes moved" in block(out)["VALUE-1"]
    assert nexts(out) == [f"des craft --repo-root {root} --value 1"]

    code, out, err = step("craft", "--repo-root", str(root), "--value", "1")

    assert code == 0, out + err
    rows = block(out)
    assert rows["DELIVERY-OUTCOME"] == "Success"
    # NO crafter turn: the terminal says so, and the provider log agrees.
    assert rows["TURNS-BOUGHT"] == "0"
    assert asked(turns) == bought_before
    # The step STATES what settled the record.
    assert rows["WITNESS"] == (
        f"the tracked oracle {ORACLE} was executed on the current workspace "
        "bytes and observed GREEN, so this value's moved craft record was "
        "re-pointed at them and no crafter turn was bought"
    )
    assert OBSERVATION in rows["VALUE-1"]
    # The record was re-pointed at the current bytes, so the order owes verify.
    assert nexts(out) == [f"des verify --repo-root {root}"]
    assert (root / TARGET).read_text() == MOVED

    code, out, _ = step("state", "--repo-root", str(root))
    assert code == 0, out
    assert "craft=recorded" in block(out)["VALUE-1"]
    assert nexts(out) == [f"des verify --repo-root {root}"]


def test_an_unrelated_commit_keeps_a_recorded_craft_current(
    root: Path, step, turns: Path
) -> None:
    """A legacy full-tree record migrates without repaying its crafter turn."""
    _walk_to_a_recorded_craft(step, root, EXISTENCE_ORACLE)
    bought_before = asked(turns)

    craft_ref = next(
        ref
        for ref in git(
            root, "for-each-ref", "--format=%(refname)", "refs/nwave/turns"
        ).splitlines()
        if ref.endswith("/craft")
    )
    message = git(root, "show", "-s", "--format=%B", craft_ref)
    legacy = git(root, "commit-tree", "HEAD^{tree}", "-p", "HEAD", "-m", message)
    git(root, "update-ref", craft_ref, legacy)

    (root / "unrelated.md").write_text("a separate request advanced HEAD\n")
    git(root, "add", "unrelated.md")
    git(root, "commit", "-qm", "separate request")

    code, out, err = step("craft", "--repo-root", str(root), "--value", "1")

    assert code == 0, out + err
    rows = block(out)
    assert rows["TURNS-BOUGHT"] == "0"
    assert asked(turns) == bought_before
    assert nexts(out) == [f"des verify --repo-root {root}"]
    assert (root / TARGET).read_text() == CRAFTED


def test_a_red_tracked_oracle_leaves_the_moved_record_unsettled_and_buys_the_turn(
    root: Path, step, turns: Path
) -> None:
    """The same walk, with an oracle the move turns RED: today's step, unchanged."""
    _walk_to_a_recorded_craft(step, root, CONTENT_ORACLE)
    bought_before = asked(turns)

    (root / TARGET).write_text(MOVED)

    code, out, err = step(
        "craft",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[_craft_answer()],
    )

    assert code == 0, out + err
    rows = block(out)
    assert rows["TURNS-BOUGHT"] == "1"
    assert rows["ROLE"] == "nw-software-crafter"
    assert asked(turns) == [*bought_before, "nw-software-crafter"]
    # A turn that was bought is not a witness: the settling row is absent.
    assert "WITNESS" not in rows


def test_an_unexecutable_tracked_oracle_leaves_the_moved_record_unsettled(
    root: Path, step, turns: Path
) -> None:
    """An oracle the runner cannot execute never authorises a skipped turn.

    No new refusal is invented for it either: an unresolved measurement degrades
    to «the turn is not complete», which is exactly what the step already does.
    """
    _walk_to_a_recorded_craft(step, root, EXISTENCE_ORACLE)
    bought_before = asked(turns)

    (root / TARGET).write_text(MOVED)
    (root / ORACLE).unlink()

    code, out, err = step(
        "craft",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[_craft_answer()],
    )

    assert code == 0, out + err
    rows = block(out)
    assert rows["TURNS-BOUGHT"] == "1"
    assert asked(turns) == [*bought_before, "nw-software-crafter"]
    assert "WITNESS" not in rows
    assert "WHAT" not in rows


def test_a_green_oracle_never_completes_a_craft_that_was_never_recorded(
    root: Path, step, turns: Path
) -> None:
    """The 2026-09-04 guard: an ABSENT record is not settled by a green oracle."""
    code, out, _ = step(
        "po",
        "--project",
        "--repo-root",
        str(root),
        stdin=REQUEST,
        answers=[accepted_values(LABEL)],
    )
    assert code == 0, out
    code, out, _ = step(
        "design", "--repo-root", str(root), "--value", "1", answers=[_design_answer()]
    )
    assert code == 0, out
    code, out, err = step(
        "oracle",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[_oracle_answer(EXISTENCE_ORACLE)],
    )
    assert code == 0, out + err

    # The production bytes are written by HAND, so the oracle is green and no
    # craft turn has ever been recorded for this value.
    (root / TARGET).parent.mkdir(parents=True, exist_ok=True)
    (root / TARGET).write_text(CRAFTED)

    code, out, _ = step("state", "--repo-root", str(root))
    assert code == 0, out
    assert "craft=absent" in block(out)["VALUE-1"]

    bought_before = asked(turns)
    code, out, err = step(
        "craft",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[_craft_answer()],
    )

    assert code == 0, out + err
    rows = block(out)
    assert rows["TURNS-BOUGHT"] == "1"
    assert asked(turns) == [*bought_before, "nw-software-crafter"]
    assert "WITNESS" not in rows


def test_an_accepted_silent_craft_records_only_after_a_green_oracle(
    root: Path, step, turns: Path
) -> None:
    """A pre-existing implementation must not repeatedly buy the same craft turn.

    The value is deliberately made green after the RED oracle has been admitted
    but before the crafter is invoked.  The crafter then accepts without writes.
    Its acceptance alone is insufficient; the runner must execute the tracked
    oracle and record the turn only when that independent native observation is
    GREEN.  The public state then owes VERIFY rather than another CRAFT.
    """
    code, out, _ = step(
        "po",
        "--project",
        "--repo-root",
        str(root),
        stdin=REQUEST,
        answers=[accepted_values(LABEL)],
    )
    assert code == 0, out
    code, out, _ = step(
        "design",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[_design_answer()],
    )
    assert code == 0, out
    code, out, err = step(
        "oracle",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[_oracle_answer(EXISTENCE_ORACLE)],
    )
    assert code == 0, out + err

    # This is the real resume shape: a prior delivery or sibling already left
    # the public behavior in place, but this value has no craft record yet.
    target = root / TARGET
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(CRAFTED)
    bought_before = asked(turns)

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
                    "diagnostic": "the admitted behavior is already present",
                }
            }
        ],
    )

    assert code == 0, out + err
    rows = block(out)
    assert rows["TURNS-BOUGHT"] == "1"
    assert asked(turns) == [*bought_before, "nw-software-crafter"]
    assert "observed GREEN, so this craft turn was recorded" in rows["SILENT"]
    assert nexts(out) == [f"des verify --repo-root {root}"]

    code, out, _ = step("state", "--repo-root", str(root))
    assert code == 0, out
    assert "craft=recorded" in block(out)["VALUE-1"]
    assert nexts(out) == [f"des verify --repo-root {root}"]

    # The record prevents a second expensive call for the same current bytes.
    code, out, err = step("craft", "--repo-root", str(root), "--value", "1")
    assert code == 0, out + err
    assert block(out)["TURNS-BOUGHT"] == "0"
    assert asked(turns) == [*bought_before, "nw-software-crafter"]


def test_an_accepted_silent_craft_stays_unrecorded_when_its_oracle_is_red(
    root: Path, step, turns: Path
) -> None:
    """A no-op cannot claim delivery merely because the role accepted it."""
    code, out, _ = step(
        "po",
        "--project",
        "--repo-root",
        str(root),
        stdin=REQUEST,
        answers=[accepted_values(LABEL)],
    )
    assert code == 0, out
    code, out, _ = step(
        "design",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[_design_answer()],
    )
    assert code == 0, out
    code, out, err = step(
        "oracle",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[_oracle_answer(CONTENT_ORACLE)],
    )
    assert code == 0, out + err

    target = root / TARGET
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(MOVED)
    bought_before = asked(turns)
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
                    "diagnostic": "no production change",
                }
            }
        ],
    )

    assert code == 0, out + err
    assert asked(turns) == [*bought_before, "nw-software-crafter"]
    assert "observed GREEN" not in block(out)["SILENT"]
    assert nexts(out) == [f"des craft --repo-root {root} --value 1"]
    code, out, _ = step("state", "--repo-root", str(root))
    assert code == 0, out
    assert "craft=absent" in block(out)["VALUE-1"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
