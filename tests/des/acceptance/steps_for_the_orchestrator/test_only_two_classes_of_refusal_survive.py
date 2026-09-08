"""A step refuses on SEQUENCE or on an unreadable state, and on nothing else.

ADR-DES-003 §2.5 closes the taxonomy to two classes. SEQUENCE: the owned state
does not admit the step -- wanted, it catches a wrong orchestrator move, and it
always says what is missing. CONTENT: the state is no longer interpretable.
Everything else a turn produces is a FACT the step measures, records and
returns: «a wrong or incomplete answer; a repeated answer; a rejecting role's
own verdict».

§2.5 applies that to the delivered code and retires four refusals with the
reason each was found to lack. This file is their executable half.

- `RequestAlreadyDecomposed` claimed content on an argument, with no incident:
  `devops` after `po` is an admissible order, so it is accepted and MEASURED as
  `DECOMPOSED-BEFORE`.
- `CraftUnrecorded` claimed sequence, but the state admits it: under §4a shared
  work is done once, so a value can be green without its own craft turn.
  `verify` runs the native verification and measures `UNCRAFTED`.
- `DesignCorrectionNoProgress` stopped a loop the composer ran. Identity of a
  model's answer with the previous one is a fact, not a hazard: `Success` with
  `UNCHANGED`.
- the pre-craft oracle judge is a FOURTH model boundary §4a retired (§5). `des
  oracle` authors and measures RED; the oracle's independent judgement is the
  whole-diff review at `verify`, which sees oracle and implementation together.
"""

from __future__ import annotations

from pathlib import Path

from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    accepted_values,
    asked,
    block,
)


REQUEST = "one Request whose steps refuse only where the state does not admit them"
AUTHORITY = "docs/product/architecture/operational-authority.md"
SECTION = "Operational constraints"
ORACLE = "tests/acceptance/test_value.py"
SUPPORT = "tests/acceptance/support.py"
TARGET = "product_value.py"
RED_ORACLE = (
    "import pathlib\nimport sys\n\n\ndef test_value():\n"
    "    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))\n"
    "    from product_value import VALUE\n\n    assert VALUE == 1\n"
)
CONSTRAINTS = (
    "# Operational authority\n\n## Operational constraints\n\n"
    "- The service exposes `/healthz` returning 200 within 500 ms.\n"
)


def design_facts(target: str = TARGET) -> dict:
    return {
        "structured_output": {
            "outcome": "accepted",
            "diagnostic": "bound the typed facts",
            "design_facts": {
                "targets": [{"path": target, "decision": "CREATE_NEW"}],
                "paradigm": "object_oriented",
                "decisions": ["one opaque semantic decision"],
                "oracle": ORACLE,
                "acceptance_supports": [SUPPORT],
                "verification": [["python", "-m", "pytest", ORACLE]],
            },
        }
    }


def authored() -> dict:
    return {
        "structured_output": {
            "outcome": "accepted",
            "diagnostic": "authored the oracle",
        },
        "writes": {ORACLE: RED_ORACLE, SUPPORT: "MARKER = 1\n"},
    }


def decomposed(root: Path, step, *labels: str) -> None:
    assert (
        step(
            "po",
            "--repo-root",
            str(root),
            answers=[accepted_values(*labels)],
            stdin=REQUEST,
        )[0]
        == 0
    )


def test_devops_after_a_decomposition_is_accepted_and_measured(
    root: Path, step
) -> None:
    """An admissible order, so the software measures it instead of refusing."""
    (root / AUTHORITY).parent.mkdir(parents=True, exist_ok=True)
    (root / AUTHORITY).write_text("# Operational authority\n")
    decomposed(root, step, "A", "B")

    code, out, err = step(
        "devops",
        "--repo-root",
        str(root),
        "--authority",
        AUTHORITY,
        "--section",
        SECTION,
        answers=[
            {
                "structured_output": {
                    "outcome": "accepted",
                    "diagnostic": "one observable operational constraint",
                },
                "writes": {AUTHORITY: CONSTRAINTS},
            }
        ],
        stdin=REQUEST,
    )

    assert code == 0, out + err
    lines = block(out, err)
    assert lines["DECOMPOSED-BEFORE"] == "2"
    assert lines["CONSTRAINTS"] == f"{AUTHORITY}#{SECTION}"


def test_an_oracle_step_buys_one_turn_and_records_on_red(
    root: Path, step, turns: Path
) -> None:
    """The pre-craft judge was a fourth model boundary; §4a keeps three."""
    decomposed(root, step, "A")
    assert (
        step(
            "design", "--repo-root", str(root), "--value", "1", answers=[design_facts()]
        )[0]
        == 0
    )
    spent = len(asked(turns))

    code, out, err = step(
        "oracle", "--repo-root", str(root), "--value", "1", answers=[authored()]
    )

    assert code == 0, out + err
    lines = block(out, err)
    assert "verdict=red" in lines["ORACLE-RED"]
    assert lines["TURNS-BOUGHT"] == "1"
    assert asked(turns)[spent:] == ["nw-acceptance-designer"]
    assert "nw-acceptance-designer-reviewer" not in asked(turns)


def test_a_repeated_design_correction_is_a_fact_not_a_hazard(root: Path, step) -> None:
    """Identity of a model's answer with the previous one is measured, not judged."""
    decomposed(root, step, "A")
    assert (
        step(
            "design", "--repo-root", str(root), "--value", "1", answers=[design_facts()]
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
    lines = block(out, err)
    assert "UNCHANGED" in lines
    assert lines["TURNS-BOUGHT"] == "1"


def test_integrating_twice_says_what_actually_happened(root: Path, step) -> None:
    """The HOW described the wrong situation: it told you to decompose a Request."""
    decomposed(root, step, "A")
    assert (
        step(
            "design", "--repo-root", str(root), "--value", "1", answers=[design_facts()]
        )[0]
        == 0
    )
    assert (
        step("oracle", "--repo-root", str(root), "--value", "1", answers=[authored()])[
            0
        ]
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
    verified = step(
        "verify",
        "--repo-root",
        str(root),
        answers=[
            {
                "structured_output": {
                    "outcome": "accepted",
                    "diagnostic": "the diff is right",
                }
            },
            {
                "structured_output": {
                    "outcome": "accepted",
                    "diagnostic": "the observation is there",
                }
            },
        ],
    )
    assert verified[0] == 0, verified[1] + verified[2]
    candidate = block(verified[1], verified[2])["CANDIDATE"]
    assert step("integrate", "--repo-root", str(root), "--candidate", candidate)[0] == 0

    code, out, err = step(
        "integrate", "--repo-root", str(root), "--candidate", candidate
    )

    assert code == 1
    lines = block(out, err)
    assert lines["WHAT"] == "AlreadyIntegrated"
    assert "decompose one Request first" not in lines["HOW"]
    assert candidate in lines["WHY"]
    assert "already the destination" in lines["WHY"]
