"""Public oracle: a MOVED oracle record is settled by the oracle's own execution.

`des oracle --value N` holds a record whose tree is the acceptance bytes it was
approved over.  When a SIBLING value's authoring turn appends to a shared
acceptance file, those bytes move and the record no longer points at them --
`des state` prints the third record state `oracle=bytes moved` and `des oracle`
used to buy a whole acceptance-designer turn to re-author what is already on
disk and already approved.

The observation here is that the oracle can WITNESS ITS OWN RECORD: when the
record EXISTS, every tracked acceptance path is still present, and the tracked
oracle executes to one of the two resolved verdicts (`red` or `green`), the turn
is complete, the record is re-pointed at the current bytes, no turn is bought,
and the terminal says which execution settled it.  Every other shape -- a
`broken` execution, a tracked support path that no longer exists, no record at
all, or an explicit `--finding -` correction -- buys the turn exactly as today.

Everything is driven through the real `des` CLI against a real Git repository
with the provider faked, because that is exactly how an orchestrator reaches it;
the provider LOG is what makes «no turn was bought» a measurement rather than a
claim.
"""

from __future__ import annotations

import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest

from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    accepted_values,
    asked,
    block,
    nexts,
)


REQUEST = "one Request whose single value carries an executable public oracle"
ORACLE = "tests/acceptance/test_value.py"
SUPPORT = "tests/acceptance/support.py"
TARGET = "src/product/value.py"

#: RED before craft and GREEN after it, and red by its own ASSERTION rather than
#: by an exception, so the authoring measurement reads `red` and never `broken`.
TRACKED_ORACLE = (
    "from pathlib import Path\n"
    "\n"
    "\n"
    "def test_value():\n"
    "    assert Path('src/product/value.py').exists()\n"
)
#: The MOVE: one appended comment line changes the acceptance tree the record
#: points at without changing what the oracle measures. This is the shape a
#: sibling value's authoring turn produces on a shared acceptance file.
MOVE = "# appended by a sibling value's authoring turn\n"
#: An oracle that never reaches its own assertion: the import is at MODULE level,
#: so collection errors and the verdict is `broken` -- not a resolved verdict,
#: and therefore no witness for anything.
BROKEN_ORACLE = (
    "import a_module_that_does_not_exist  # noqa\n"
    "\n"
    "\n"
    "def test_value():\n"
    "    assert True\n"
)

WITNESS = (
    f"the tracked oracle {ORACLE} was executed on the current workspace bytes "
    "and RESOLVED to its own verdict, so this value's moved oracle record was "
    "re-pointed at them and no acceptance-designer turn was bought"
)


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
                # A tracked path that is NOT the oracle, so path EXISTENCE can be
                # falsified independently of the verdict.
                "acceptance_supports": [SUPPORT],
                "verification": [[sys.executable, "-m", "pytest", ORACLE]],
                "oracle_verification_index": 0,
            },
        }
    }


def authored(body: str = TRACKED_ORACLE, support: str = "MARKER = 1\n") -> dict:
    return {
        "structured_output": {"outcome": "accepted", "diagnostic": "authored it"},
        "writes": {ORACLE: body, SUPPORT: support},
    }


def bound(root: Path, step) -> None:
    """Decompose and bind, so the value carries what the oracle step consumes."""
    code, out, err = step(
        "po",
        "--project",
        "--repo-root",
        str(root),
        answers=[accepted_values("A")],
        stdin=REQUEST,
    )
    assert code == 0, out + err
    code, out, err = step(
        "design", "--repo-root", str(root), "--value", "1", answers=[design_facts()]
    )
    assert code == 0, out + err


def recorded_over(root: Path, step) -> None:
    """One approved, recorded oracle turn -- the state the move happens from."""
    bound(root, step)
    code, out, err = step(
        "oracle", "--repo-root", str(root), "--value", "1", answers=[authored()]
    )
    assert code == 0, out + err


def move_the_bytes(root: Path) -> None:
    (root / ORACLE).write_text(TRACKED_ORACLE + MOVE)


def make_green(root: Path) -> None:
    """The craft-side bytes the tracked oracle asserts on, in the WORKSPACE."""
    target = root / TARGET
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("VALUE = 1\n")


@pytest.mark.parametrize("verdict", ["red", "green"])
def test_a_moved_record_is_settled_by_its_own_resolved_execution(
    root: Path, step, turns: Path, verdict: str
) -> None:
    """Either resolved verdict witnesses the record; neither buys a turn."""
    recorded_over(root, step)
    move_the_bytes(root)
    if verdict == "green":
        make_green(root)

    moved = step("state", "--repo-root", str(root))
    assert moved[0] == 0, moved[1] + moved[2]
    assert "oracle=bytes moved" in moved[1] + moved[2]
    spent = len(asked(turns))

    code, out, err = step("oracle", "--repo-root", str(root), "--value", "1")

    assert code == 0, out + err
    lines = block(out, err)
    assert lines["DELIVERY-OUTCOME"] == "Success"
    assert lines["TURNS-BOUGHT"] == "0"
    assert len(asked(turns)) == spent
    assert f"verdict={verdict}" in lines["ORACLE-RED"]
    assert lines["WITNESS"] == WITNESS
    assert nexts(out) == [f"des craft --repo-root {root} --value 1"]
    # The bytes the operator can read are the ones that were on disk.
    assert (root / ORACLE).read_text() == TRACKED_ORACLE + MOVE

    settled = step("state", "--repo-root", str(root))
    assert "oracle=recorded" in settled[1] + settled[2]


def test_an_execution_that_did_not_resolve_buys_the_turn_as_today(
    root: Path, step, turns: Path
) -> None:
    """`broken` is not a verdict -- it is the absence of one, so it witnesses nothing."""
    recorded_over(root, step)
    (root / ORACLE).write_text(BROKEN_ORACLE)
    spent = len(asked(turns))

    code, out, err = step(
        "oracle", "--repo-root", str(root), "--value", "1", answers=[authored()]
    )

    assert code == 0, out + err
    assert asked(turns)[spent:] == ["nw-acceptance-designer"]
    assert "WITNESS" not in block(out, err)


def test_a_missing_tracked_acceptance_path_buys_the_turn_even_when_green(
    root: Path, step, turns: Path
) -> None:
    """Existence is its own gate: a green verdict does not restore a deleted support."""
    recorded_over(root, step)
    move_the_bytes(root)
    make_green(root)
    (root / SUPPORT).unlink()
    spent = len(asked(turns))

    code, out, err = step(
        "oracle", "--repo-root", str(root), "--value", "1", answers=[authored()]
    )

    assert code == 0, out + err
    lines = block(out, err)
    assert asked(turns)[spent:] == ["nw-acceptance-designer"]
    assert "WITNESS" not in lines
    assert "WHAT" not in lines


def test_acceptance_bytes_without_a_record_are_never_a_settled_turn(
    root: Path, step, turns: Path
) -> None:
    """Bytes that satisfy an assertion are no evidence that a turn was approved."""
    bound(root, step)
    (root / ORACLE).parent.mkdir(parents=True, exist_ok=True)
    (root / ORACLE).write_text(TRACKED_ORACLE)
    (root / SUPPORT).write_text("MARKER = 1\n")
    spent = len(asked(turns))

    code, out, err = step(
        "oracle", "--repo-root", str(root), "--value", "1", answers=[authored()]
    )

    assert code == 0, out + err
    assert asked(turns)[spent:] == ["nw-acceptance-designer"]
    assert "WITNESS" not in block(out, err)


def test_a_correction_is_bought_over_a_moved_record_regardless_of_execution(
    root: Path, step, turns: Path
) -> None:
    """Re-opening an approved oracle is the orchestrator's call, not a record's."""
    recorded_over(root, step)
    move_the_bytes(root)
    spent = len(asked(turns))

    code, out, err = step(
        "oracle",
        "--repo-root",
        str(root),
        "--value",
        "1",
        "--finding",
        "-",
        stdin="the oracle asserts a field the declared public port does not expose",
        answers=[authored(TRACKED_ORACLE + "# corrected\n", "MARKER = 2\n")],
    )

    assert code == 0, out + err
    assert asked(turns)[spent:] == ["nw-acceptance-designer"]
    assert "WITNESS" not in block(out, err)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
