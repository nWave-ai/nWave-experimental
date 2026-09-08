"""Public oracle: `des design --value N`, one architect turn invoked alone.

ADR-SSOT-002 Section 4b names the step by PROPERTY -- «One role turn under a
provider-enforced typed contract: takes the role, the minimum facts that role
consumes, the private workspace; returns the closed outcome, the role's typed
output, its diagnostic verbatim.»

Three properties are measured here rather than argued.  The step buys EXACTLY
one turn and executes nothing its own `NEXT` names.  It is REPEATABLE: a second
invocation over a bound value carries a finding and REPLACES the typed facts,
which is the correction the orchestrator decides on, not an edge the software
takes.  And a refusing turn forwards the architect's own words and names both
available moves without ranking them.
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    accepted_values,
    asked,
    block,
    nexts,
)


REQUEST = "one Request whose single value the architect binds typed facts to"
HANDOVER = Path(".nwave") / "des" / "handover.json"
ORACLE = "tests/acceptance/test_value.py"
SUPPORT = "tests/acceptance/support.py"
TARGET = "src/product/value.py"


def design_facts(target: str = TARGET, decision: str = "CREATE_NEW") -> dict:
    return {
        "structured_output": {
            "outcome": "accepted",
            "diagnostic": "bound the value to its typed design facts",
            "design_facts": {
                "targets": [{"path": target, "decision": decision}],
                "paradigm": "object_oriented",
                "decisions": ["one opaque semantic decision"],
                "oracle": ORACLE,
                "acceptance_supports": [SUPPORT],
                "verification": [["bin/verify"]],
            },
        }
    }


def decomposed(root: Path, step) -> None:
    code, out, err = step(
        "po", "--repo-root", str(root), answers=[accepted_values("A")], stdin=REQUEST
    )
    assert code == 0, out + err


def authority(root: Path) -> str | None:
    stored = json.loads((root / HANDOVER).read_text())
    return stored["values"][0]["authority"]


def test_an_accepted_turn_binds_the_typed_facts_and_names_the_oracle_step(
    root: Path, step, turns: Path
) -> None:
    decomposed(root, step)
    code, out, err = step(
        "design", "--repo-root", str(root), "--value", "1", answers=[design_facts()]
    )
    assert code == 0, out + err
    lines = block(out, err)
    assert lines["DELIVERY-OUTCOME"] == "Success"
    assert "bound the value to its typed design facts" in lines["DIAGNOSTIC"]
    assert nexts(out) == [f"des oracle --repo-root {root} --value 1"]
    bound = authority(root)
    assert bound is not None
    assert bound["oracle"] == ORACLE
    assert bound["targets"] == [{"path": TARGET, "decision": "CREATE_NEW"}]
    assert asked(turns) == ["nw-product-owner", "nw-solution-architect"]


def test_a_second_turn_with_a_finding_replaces_the_bound_facts(
    root: Path, step, turns: Path
) -> None:
    """Correction is a REPEAT of the same step, decided by the orchestrator."""
    decomposed(root, step)
    step("design", "--repo-root", str(root), "--value", "1", answers=[design_facts()])
    assert authority(root)["targets"][0]["path"] == TARGET

    code, out, err = step(
        "design",
        "--repo-root",
        str(root),
        "--value",
        "1",
        "--finding",
        "-",
        answers=[design_facts(target="src/product/other.py")],
        stdin="the declared target does not exist in this repository",
    )

    assert code == 0, out + err
    assert authority(root)["targets"][0]["path"] == "src/product/other.py"
    assert asked(turns) == [
        "nw-product-owner",
        "nw-solution-architect",
        "nw-solution-architect",
    ]
    forwarded = json.loads(turns.read_text())[-1]["prompt"]
    assert "the declared target does not exist" in forwarded


def test_a_correction_repeating_the_current_facts_is_measured_not_refused(
    root: Path, step
) -> None:
    """ADR-DES-003 §2.5: identity of an answer with the previous one is a FACT.

    The refusal it replaces existed to stop a loop the composer ran, and the
    composer no longer decides. The census had already ruled it: software
    measures identity, the model decides what identity means.
    """
    decomposed(root, step)
    step("design", "--repo-root", str(root), "--value", "1", answers=[design_facts()])
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
    assert "UNCHANGED" in block(out, err)


def test_a_rejecting_turn_forwards_the_architect_words_and_ranks_no_move(
    root: Path, step, turns: Path
) -> None:
    decomposed(root, step)
    finding = (
        "this value's observation names two outcomes, so no single design binds it"
    )
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
                    "diagnostic": finding,
                    "design_facts": None,
                }
            }
        ],
    )
    assert code == 1
    lines = block(out, err)
    assert lines["DELIVERY-OUTCOME"] == "Refusal"
    assert lines["WHAT"] == "DesignRejected"
    assert "names two outcomes" in lines["DIAGNOSTIC"]
    assert authority(root) is None
    assert asked(turns) == ["nw-product-owner", "nw-solution-architect"]
    moves = nexts(out)
    assert len(moves) > 1
    assert any(item.startswith(f"des state --repo-root {root}") for item in moves)


def test_a_value_position_outside_the_graph_is_refused_before_a_turn_is_bought(
    root: Path, step, turns: Path
) -> None:
    decomposed(root, step)
    code, out, err = step(
        "design", "--repo-root", str(root), "--value", "9", answers=[design_facts()]
    )
    assert code == 1
    lines = block(out, err)
    assert lines["WHAT"] == "ValueOutOfRange"
    assert "1" in lines["WHY"]
    assert asked(turns) == ["nw-product-owner"]


def test_designing_before_any_decomposition_is_refused_and_names_the_owner(
    root: Path, step, turns: Path
) -> None:
    code, out, err = step(
        "design", "--repo-root", str(root), "--value", "1", answers=[design_facts()]
    )
    assert code == 1
    lines = block(out, err)
    assert lines["WHAT"] == "HandoverAbsent"
    assert asked(turns) == []
    assert any(item.startswith(f"des po --repo-root {root}") for item in nexts(out))


def test_the_design_terminal_states_what_the_algebra_obligation_rests_on(
    root: Path, step
) -> None:
    """Section 1a item 6, said out loud in both directions.

    Discord feedback, 2026-09-05: a tool absent without a warning. Algebra-driven
    design is a non-inferiority obligation, and whether anything can CHECK it
    mechanically is a fact about this environment, not about this Request. A
    terminal that stays silent teaches the reader that silence means met.
    """
    decomposed(root, step)
    code, out, err = step(
        "design", "--repo-root", str(root), "--value", "1", answers=[design_facts()]
    )
    assert code == 0, out + err
    line = block(out, err)["ALGEBRA"]
    assert "Section 1a item 6" in line
    assert ("INDETERMINATE" in line) or ("on PATH" in line)
