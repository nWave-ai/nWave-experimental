"""No step's ORCHESTRATOR line points at a row the terminal does not carry.

MEASURED, 2026-09-06, on `des craft --value 2` against a Request whose second
value has no bound design: the terminal refused `DesignUnbound` -- a SOFTWARE
refusal, before any turn was bought -- and told its reader «read BLOCKED-BY and
the DIAGNOSTIC below», neither of which was printed. `des oracle` did the same
naming DEFECT-OWNER, and `des design` naming a refusing architect that never
ran.

It is the same class as the defect this repository already records for a HOW
that names a repair the reader cannot perform, and as the earlier fix that gave
each step two directions instead of one: a terminal that describes rows it does
not have is a rejection that lies, and a reader who looks for them and finds
nothing learns to stop reading the line.

SIX steps carried it -- `po`, `design`, `oracle`, `craft`, `verify`, `devops` --
which is why the repair is one derivation in the shared terminal rather than six
edited sentences. A step now supplies only the MOVE a refusing role leaves; the
terminal decides what to name from the rows it is actually printing, so a step
that names an absent row is unrepresentable (GDP-0).
"""

from __future__ import annotations

import sys
from pathlib import Path

from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    accepted_values,
    asked,
    block,
)


REQUEST = "one Request whose second value is never designed"
AUTHORITY = "docs/product/architecture/operational-authority.md"
ORACLE = "tests/acceptance/test_value.py"
SUPPORT = "tests/acceptance/support.py"
TARGET = "product_value.py"
RED_ORACLE = "def test_value():\n    import product_value  # noqa\n"


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
                "verification": [[sys.executable, "-m", "pytest", ORACLE]],
                "oracle_verification_index": 0,
            },
        }
    }


def designed(root: Path, step) -> None:
    """A Request whose first value carries bound typed facts."""
    two_values(root, step)
    assert (
        step(
            "design", "--repo-root", str(root), "--value", "1", answers=[design_facts()]
        )[0]
        == 0
    )


def crafted_to_the_blocker(root: Path, step) -> None:
    """The state a craft turn is bought from: bound facts and an admitted oracle."""
    designed(root, step)
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
                },
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": "the oracle set is admissible",
                    }
                },
            ],
        )[0]
        == 0
    )


def two_values(root: Path, step) -> None:
    assert (
        step(
            "po",
            "--project",
            "--repo-root",
            str(root),
            answers=[accepted_values("A", "B")],
            stdin=REQUEST,
        )[0]
        == 0
    )


def orchestrator_line(out: str, err: str) -> str:
    return block(out, err)["ORCHESTRATOR"]


def carried(out: str, err: str, label: str) -> bool:
    return any(
        line.startswith(f"{label}: ") for line in (out + "\n" + err).splitlines()
    )


def test_a_software_refusal_never_tells_the_reader_to_read_a_role(
    root: Path, step, turns: Path
) -> None:
    """The measured case: no turn was bought, so there is nothing of a role's."""
    two_values(root, step)
    spent = len(asked(turns))
    for argv in (
        ("craft", "--repo-root", str(root), "--value", "2"),
        ("oracle", "--repo-root", str(root), "--value", "2"),
        ("design", "--repo-root", str(root), "--value", "9"),
        ("verify", "--repo-root", str(root)),
    ):
        code, out, err = step(*argv)
        assert code == 1, argv
        line = orchestrator_line(out, err)
        assert "DIAGNOSTIC" not in line, (argv, line)
        assert "BLOCKED-BY" not in line, (argv, line)
        assert "DEFECT-OWNER" not in line, (argv, line)
        assert "no role turn ran" in line, (argv, line)
    assert len(asked(turns)) == spent


def test_a_refusing_role_without_a_named_word_points_only_at_its_diagnostic(
    root: Path, step
) -> None:
    two_values(root, step)
    code, out, err = step(
        "design",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[
            {
                "structured_output": {
                    "outcome": "rejected",
                    "diagnostic": "this observation names two outcomes",
                    "design_facts": None,
                }
            }
        ],
    )
    assert code == 1
    line = orchestrator_line(out, err)
    assert "DIAGNOSTIC" in line
    assert "BLOCKED-BY" not in line
    assert "DEFECT-OWNER" not in line
    assert carried(out, err, "DIAGNOSTIC")


def test_a_step_refused_on_its_argument_shape_says_no_turn_ran(
    root: Path, step
) -> None:
    """`des devops` with an inadmissible authority buys nothing and says so."""
    two_values(root, step)
    code, out, err = step(
        "devops",
        "--project",
        "--repo-root",
        str(root),
        "--authority",
        "../escape.md",
        "--section",
        "Operational constraints",
        stdin=REQUEST,
    )
    assert code == 1
    assert block(out, err)["WHAT"] == "AuthorityInadmissible"
    line = orchestrator_line(out, err)
    assert "DIAGNOSTIC" not in line
    assert "no role turn ran" in line


def test_a_terminal_carrying_blocked_by_points_at_it(root: Path, step) -> None:
    """The POSITIVE half: a row that IS printed must be named.

    Without this the derivation could name nothing at all and stay green, which
    is what a review measured: mutating `refusal_direction` to never name
    BLOCKED-BY or DEFECT-OWNER left 200 tests passing.
    """
    crafted_to_the_blocker(root, step)
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
                    "diagnostic": "the failing line lives in the immutable oracle",
                    "blocked_by": "oracle",
                }
            }
        ],
    )
    assert code == 1
    assert carried(out, err, "BLOCKED-BY")
    line = orchestrator_line(out, err)
    assert "BLOCKED-BY" in line
    assert "DIAGNOSTIC" in line
    assert "DEFECT-OWNER" not in line
    assert "no role turn ran" not in line


#: The `DEFECT-OWNER` instance that stood here drove the pre-craft oracle judge,
#: which ADR-DES-003 §5 retires as a fourth model boundary. Its replacement
#: producer is the whole-diff reviewer at `verify`, which §6 gives the measured
#: radius and the ability to charge a finding to the oracle -- a change to that
#: role's envelope schema, owed by the radius slice. Until it lands the row has
#: no step-reachable producer, and the DERIVATION that names it stays covered
#: directly in `tests/des/unit/cli/test_step_terminal_refusal_direction.py`.
#: Recorded here rather than deleted silently, so the gap is visible.


def test_a_turn_that_was_bought_is_never_reported_as_unbought(
    root: Path, step, turns: Path
) -> None:
    """MEASURED 2026-09-06: a paid turn reported as no turn at all.

    A Product Owner answering with an envelope the boundary refuses leaves no
    `ModelRun`, so a direction derived from "is there a diagnostic" said the
    software had refused before buying one -- while the provider log shows the
    turn was bought. It is the class `ProviderSpawnFailed` already names: a
    rejection that lies about its own cause. The discriminating fact is the
    turn whose PROCESS ran, and the provider log is the second axis that says
    so independently of the terminal.
    """
    code, out, err = step(
        "po",
        "--project",
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
    assert asked(turns) == ["nw-product-owner"]
    assert "no role turn ran" not in orchestrator_line(out, err)
