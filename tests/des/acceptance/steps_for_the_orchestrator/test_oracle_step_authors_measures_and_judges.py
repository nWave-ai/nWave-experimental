"""Public oracle: `des oracle --value N`, the executable oracle for one value.

ONE PAID TURN, and the second one was RETIRED. Authoring and measuring RED are
two things the software does to the same artefact, and between them the
orchestrator has no decision to make. It DID have one between «measured» and
«judged», and the delivered step denied it by buying a pre-craft judge --
a FOURTH model boundary, where ADR-SSOT-002 §4a names exactly three and lists
the pre-craft oracle review among the mechanisms that lapse (ADR-DES-003 §5).

The oracle's independent judgement is now the whole-diff review at `verify`,
which sees oracle and implementation together. Run 23's lesson -- a judge
approving a broken oracle in 27.4s of paid turn -- is answered by the RED
measurement, which is software, free, and runs here. Craft-time oracle defects
still come back as `BLOCKED-BY: oracle` to `des oracle --finding -`.
"""

from __future__ import annotations

import sys
from pathlib import Path

from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    accepted_values,
    asked,
    block,
    git,
    nexts,
)


REQUEST = "one Request whose single value carries an executable public oracle"
HANDOVER = Path(".nwave") / "des" / "handover.json"
ORACLE = "tests/acceptance/test_value.py"
SUPPORT = "tests/acceptance/support.py"
TARGET = "src/product/value.py"

#: An oracle that FAILS on its own assertion, which is the admitted answer
#: before any production byte exists: the import happens inside the test body,
#: so pytest records a FAILURE and zero errors.
RED_ORACLE = "def test_value():\n    import product.value  # noqa\n"
#: An oracle that never reaches its own assertion -- the import is at module
#: level, so collection ERRORS and the verdict is `broken`. This is the class
#: measured twice on 2026-09-05 (runs 22 and 23), where a broken oracle was
#: APPROVED by a paid judgement and refused three turns later.
BROKEN_ORACLE = (
    "import product.value  # noqa\n\n\ndef test_value():\n    assert False\n"
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
                "acceptance_supports": [SUPPORT],
                "verification": [[sys.executable, "-m", "pytest", ORACLE]],
                "oracle_verification_index": 0,
            },
        }
    }


def authored(body: str = RED_ORACLE, diagnostic: str = "authored the oracle") -> dict:
    return {
        "structured_output": {"outcome": "accepted", "diagnostic": diagnostic},
        "writes": {ORACLE: body, SUPPORT: "MARKER = 1\n"},
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


def turn_refs(root: Path) -> list[str]:
    listed = git(root, "for-each-ref", "--format=%(refname)", "refs/nwave/turns")
    return [line for line in listed.splitlines() if line]


def test_an_admitted_oracle_is_measured_red_judged_and_recorded(
    root: Path, step, turns: Path
) -> None:
    bound(root, step)
    code, out, err = step(
        "oracle",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[authored()],
    )
    assert code == 0, out + err
    lines = block(out, err)
    assert lines["DELIVERY-OUTCOME"] == "Success"
    assert "ORACLE-RED" in lines
    assert ORACLE in lines["ORACLE-RED"]
    assert (root / ORACLE).read_text() == RED_ORACLE
    assert asked(turns)[-1] == "nw-acceptance-designer"
    assert "nw-acceptance-designer-reviewer" not in asked(turns)
    assert any(ref.endswith("/oracle") for ref in turn_refs(root))
    assert nexts(out) == [f"des craft --repo-root {root} --value 1"]


def test_a_broken_oracle_is_refused_before_any_judgement_is_bought(
    root: Path, step, turns: Path
) -> None:
    """The free measurement runs first, so no paid turn judges a broken oracle."""
    bound(root, step)
    code, out, err = step(
        "oracle",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[authored(BROKEN_ORACLE)],
    )
    assert code == 1, out + err
    lines = block(out, err)
    assert lines["WHAT"] == "OracleNotRed"
    assert "verdict=broken" in lines["ORACLE-RED"]
    assert asked(turns)[-1] == "nw-acceptance-designer"
    assert not any(ref.endswith("/oracle") for ref in turn_refs(root))


def test_a_recorded_oracle_turn_is_a_resume_and_buys_nothing(
    root: Path, step, turns: Path
) -> None:
    bound(root, step)
    first = step(
        "oracle",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[authored()],
    )
    assert first[0] == 0, first[1] + first[2]
    spent = len(asked(turns))

    code, out, err = step(
        "oracle",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[authored()],
    )

    assert code == 0, out + err
    assert len(asked(turns)) == spent


def test_an_unbound_value_is_refused_and_names_the_architect_step(
    root: Path, step, turns: Path
) -> None:
    code, out, err = step(
        "po",
        "--project",
        "--repo-root",
        str(root),
        answers=[accepted_values("A")],
        stdin=REQUEST,
    )
    assert code == 0, out + err
    code, out, err = step("oracle", "--repo-root", str(root), "--value", "1")
    assert code == 1
    lines = block(out, err)
    assert lines["WHAT"] == "DesignUnbound"
    assert any(
        item.startswith(f"des design --repo-root {root} --value 1")
        for item in nexts(out)
    )
    assert asked(turns) == ["nw-product-owner"]
