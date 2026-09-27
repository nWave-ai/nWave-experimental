"""Public oracle: the LLM owns S/M/L and the route; the DES only constructs.

`F-DES-SML-GOVERNS-FLOW`. The Request's size and the path it takes are the
orchestrator's judgment, revised whenever evidence changes. The software's whole
part is deterministic construction from the parameters it was handed, plus an
advisory `NEXT`. So there is no size to hand it, no size-to-path mapping for it
to apply, and no step it admits or refuses because of where a route "should" be.

What is measured here rather than argued:

  * no public step takes a size, so a classification cannot even be expressed to
    the software, and none is bought;
  * the orchestrator takes a supported step the terminal did NOT name, and the
    step performs it, which is what makes `NEXT` advisory rather than a fork
    controller;
  * a RECLASSIFICATION -- the same work re-cut into a different number of values
    -- is constructed, not adjudicated;
  * an UPSTREAM RETURN over an already bound value re-binds on the orchestrator's
    finding, with nothing between the decision and the construction.

Every terminal in this corpus is also read for a size label, because a step that
printed one would be teaching a route the orchestrator did not choose.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from des.cli.__main__ import _REGISTRY
from tests.common.in_process_cli import run_cli_in_process
from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    accepted_values,
    asked,
    block,
    nexts,
    observation,
)


FIRST = "one Request the orchestrator judged deliverable as a single value"
RECUT = "the same work, re-judged and re-cut into two ordered values"
HANDOVER = Path(".nwave") / "des" / "handover.json"
ORACLE = "tests/acceptance/test_value.py"
SUPPORT = "tests/acceptance/support.py"
TARGET = "src/product/value.py"

#: A size label as a step could print it: a bare S, M or L standing alone as a
#: verdict about the Request. Matched on word boundaries so ordinary prose that
#: happens to contain those letters is not mistaken for a classification.
SIZE_LABEL = re.compile(r"(?<![\w-])(?:S|M|L)(?![\w-])")


def design_facts(target: str = TARGET) -> dict:
    return {
        "structured_output": {
            "outcome": "accepted",
            "diagnostic": "bound the value to its typed design facts",
            "design_facts": {
                "targets": [{"path": target, "decision": "CREATE_NEW"}],
                "paradigm": "object_oriented",
                "decisions": ["one opaque semantic decision"],
                "oracle": ORACLE,
                "acceptance_supports": [SUPPORT],
                "verification": [[sys.executable, "-m", "pytest", ORACLE]],
                "oracle_verification_index": 0,
            },
        }
    }


def stored(root: Path) -> dict:
    return json.loads((root / HANDOVER).read_text())


def carries_no_size_verdict(out: str, err: str) -> bool:
    """No label in the terminal is a size classification of the Request."""
    return not any(SIZE_LABEL.search(value) for value in block(out, err).values())


#: An option by which a size could be handed to the software. Named by shape
#: rather than by one spelling, because the claim is about classification and
#: not about the four letters someone happened to choose.
SIZE_OPTION = re.compile(r"--[a-z0-9-]*(?:size|tier|sml)[a-z0-9-]*")


def help_text(argv: list[str], cwd: Path) -> str:
    return "".join(run_cli_in_process([*argv, "--help"], cwd=cwd, catch_all=True)[1:])


def public_invocation_forms(cwd: Path) -> list[list[str]]:
    """Every form the installed CLI exposes, read from its own registry.

    Derived and never listed, so a command added tomorrow is covered the day it
    is registered rather than the day somebody remembers this corpus. A row
    whose help offers a choice of sub-forms contributes each of them.
    """
    forms: list[list[str]] = []
    for row in _REGISTRY:
        offered = re.search(r"\{([a-z0-9,-]+)\}", help_text([row.name], cwd))
        if offered:
            forms.extend([row.name, sub] for sub in offered.group(1).split(","))
        else:
            forms.append([row.name])
    return forms


def test_no_public_command_offers_a_size_on_its_own_surface(root: Path) -> None:
    """The claim is universal, so it is measured over the whole registry."""
    forms = public_invocation_forms(root)
    assert len(forms) >= len(_REGISTRY)
    offending = {
        " ".join(form): SIZE_OPTION.findall(help_text(form, root)) for form in forms
    }
    assert not {name: hits for name, hits in offending.items() if hits}


def test_a_size_handed_to_a_step_is_rejected_and_buys_no_turn(
    root: Path, step, turns: Path
) -> None:
    """A classification cannot be expressed to the software at all."""
    for argv in (
        ("po", "--project", "--repo-root", str(root), "--size", "S"),
        ("design", "--repo-root", str(root), "--value", "1", "--size", "L"),
        ("craft", "--repo-root", str(root), "--value", "1", "--size", "M"),
        ("state", "--repo-root", str(root), "--size", "M"),
    ):
        code, out, err = step(*argv, answers=[accepted_values("A")], stdin=FIRST)
        assert code != 0, argv
        assert "--size" in out + err, argv
    assert asked(turns) == []
    assert not (root / HANDOVER).exists()


def test_the_orchestrator_may_take_a_supported_step_the_terminal_did_not_name(
    root: Path, step
) -> None:
    """`NEXT` is advisory data: the step it does not name is performed anyway."""
    code, out, err = step(
        "po",
        "--project",
        "--repo-root",
        str(root),
        answers=[accepted_values("A", "B")],
        stdin=RECUT,
    )
    assert code == 0, out + err
    suggested = nexts(out)
    assert suggested == [f"des design --repo-root {root} --value 1"]

    code, out, err = step(
        "design", "--repo-root", str(root), "--value", "2", answers=[design_facts()]
    )

    assert code == 0, out + err
    assert block(out, err)["DELIVERY-OUTCOME"] == "Success"
    assert stored(root)["values"][1]["authority"]["oracle"] == ORACLE
    assert stored(root)["values"][0]["authority"] is None


def test_a_reclassification_is_constructed_and_never_adjudicated(
    root: Path, step
) -> None:
    """Re-cutting one value into two costs one turn and no admission."""
    assert (
        step(
            "po",
            "--project",
            "--repo-root",
            str(root),
            answers=[accepted_values("A")],
            stdin=FIRST,
        )[0]
        == 0
    )

    code, out, err = step(
        "po",
        "--project",
        "--repo-root",
        str(root),
        answers=[accepted_values("A", "B")],
        stdin=RECUT,
    )

    assert code == 0, out + err
    lines = block(out, err)
    assert lines["DELIVERY-OUTCOME"] == "Success"
    assert lines["TURNS-BOUGHT"] == "1"
    assert [value["observation"] for value in stored(root)["values"]] == [
        observation("A"),
        observation("B"),
    ]
    assert carries_no_size_verdict(out, err)


def test_an_upstream_return_over_a_bound_value_rebinds_on_the_finding(
    root: Path, step, turns: Path
) -> None:
    """Going back upstream needs a decision, not a permitted transition."""
    assert (
        step(
            "po",
            "--project",
            "--repo-root",
            str(root),
            answers=[accepted_values("A")],
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

    code, out, err = step(
        "design",
        "--repo-root",
        str(root),
        "--value",
        "1",
        "--finding",
        "-",
        answers=[design_facts(target="src/product/other.py")],
        stdin="the bound target is owned by an authority this value does not hold",
    )

    assert code == 0, out + err
    assert stored(root)["values"][0]["authority"]["targets"] == [
        {"path": "src/product/other.py", "decision": "CREATE_NEW"}
    ]
    assert asked(turns).count("nw-solution-architect") == 2
    assert carries_no_size_verdict(out, err)
