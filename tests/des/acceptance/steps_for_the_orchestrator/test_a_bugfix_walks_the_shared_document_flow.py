"""Public oracle: an observed defect walks the SAME steps a feature walks.

`F-DES-BUGFIX-DOCUMENT-FLOW`. There is no bugfix pipeline and there must never
be one: the fix enters through the typed document producers -- DISCUSS, DESIGN,
DISTILL -- reaches its regression oracle through `des oracle`, its correction
through `des craft`, and its verified candidate through `des verify`. What this
corpus measures is the LINK: the observed defect the human reported survives
into the durable DISCUSS authority, the same observation names the regression
obligation the DISTILL authority binds, and the candidate that closes the
Request carries the correction those two documents describe.

The defect is real rather than narrated. The base commit carries a module whose
public value is wrong, the oracle authored against it is measured RED by the
software, and the crafted correction is what turns it GREEN.
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    asked,
    block,
    git,
)


#: The human's words, verbatim, which is what a durable authority owes back.
OBSERVED_DEFECT = (
    "the installed command reports value 2 where the published contract states value 1"
)
CORRECTED_OBSERVATION = (
    "the installed command observably reports value 1 for the published contract"
)

TARGET = "product_value.py"
ORACLE = "tests/acceptance/test_regression.py"
SUPPORT = "tests/acceptance/support.py"
DISCUSS_DESTINATION = "docs/product/defect-brief.md"
DESIGN_DESTINATION = "docs/product/architecture/defect-brief.md"

BUGGY = "VALUE = 2\n"
CORRECTED = "VALUE = 1\n"

REGRESSION_ORACLE = (
    "import pathlib\n"
    "import sys\n"
    "\n"
    "\n"
    "def test_the_reported_defect_no_longer_occurs():\n"
    "    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))\n"
    "    from product_value import VALUE\n"
    "\n"
    "    assert VALUE == 1\n"
)


def discuss_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "request": OBSERVED_DEFECT,
        "outcomes": [f"The reported defect no longer occurs: {OBSERVED_DEFECT}."],
        "scope": {
            "in_scope": ["The published value the defect report names."],
            "out_of_scope": {
                "applicability": "not_applicable",
                "reason": "The defect is contained in one published value.",
                "items": [],
            },
        },
        "decisions": ["Correct the published value where it is already owned."],
        "values": [{"observation": CORRECTED_OBSERVATION, "dependencies": []}],
    }


def design_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "authority": {"heading": "Reported defect in the published value"},
        "purpose": "Correct the published value the defect report names.",
        "constraints": ["Preserve every other published value."],
        "targets": [
            {
                "path": TARGET,
                "decision": "EXTEND",
                "reason": "The module already owns the published value.",
            }
        ],
        "paradigm": "object_oriented",
        "decisions": ["Correct the value in the module that already owns it."],
        "reuse_analysis": {
            "candidates": [
                {
                    "symbol": "VALUE",
                    "locator": f"{TARGET}:1",
                    "decision": "EXTEND",
                    "reason": "The defective public symbol.",
                }
            ]
        },
        "prefactoring": {
            "applicability": "not_applicable",
            "reason": "The correction needs no structural move.",
        },
        "agreement_analysis": {
            "applicability": "not_applicable",
            "reason": "The correction touches no shared release or interchange schema.",
        },
        "boundaries": {
            "applicability": "not_applicable",
            "reason": "No port or dependency boundary changes.",
        },
        "public_oracle": {
            "observation": CORRECTED_OBSERVATION,
            "stimulus": "Read the published value.",
            "expected": "The published value is 1.",
            "falsifier": "Any other published value.",
        },
        "oracle": ORACLE,
        "acceptance_supports": [SUPPORT],
        "verification": [["python", "-m", "pytest", ORACLE]],
    }


def distill_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "values": [
            {
                "observation": CORRECTED_OBSERVATION,
                "acceptance_obligations": [
                    {
                        "id": "reported-defect-does-not-recur",
                        "stimulus": OBSERVED_DEFECT,
                        "expected": "The published value is 1.",
                    }
                ],
                "oracle": ORACLE,
                "acceptance_supports": [SUPPORT],
            }
        ],
    }


def authored_regression_oracle() -> dict:
    return {
        "structured_output": {
            "outcome": "accepted",
            "diagnostic": "authored the regression oracle for the reported defect",
        },
        "writes": {ORACLE: REGRESSION_ORACLE, SUPPORT: "MARKER = 1\n"},
    }


def crafted_correction() -> dict:
    return {
        "structured_output": {
            "outcome": "accepted",
            "diagnostic": "corrected the published value behind its regression oracle",
        },
        "writes": {TARGET: CORRECTED},
    }


def role_result(role: str, outcome: str) -> str:
    payload: dict[str, object] = {"outcome": outcome, "diagnostic": f"host {role}"}
    if role == "reviewer":
        payload |= {"defect_owner": None, "defect_value": None}
    return json.dumps({"structured_output": payload})


def observed(root: Path, step, role: str, candidate: str) -> dict[str, str]:
    assert (
        step(
            "prepare-role",
            "--repo-root",
            str(root),
            "--role",
            role,
            "--candidate",
            candidate,
        )[0]
        == 0
    )
    code, out, err = step(
        "record-role-result",
        "--repo-root",
        str(root),
        "--role",
        role,
        "--candidate",
        candidate,
        "--provider",
        "claude",
        "--model",
        "host-observation-model",
        "--session-id",
        f"bugfix-{role}",
        "--input",
        "-",
        stdin=role_result(role, "accepted"),
    )
    assert code == 0, out + err
    return block(out, err)


def defective_repository(root: Path) -> None:
    """The reported defect, committed, so the oracle measures a real failure."""
    (root / TARGET).write_text(BUGGY)
    (root / ".nwave").mkdir(exist_ok=True)
    (root / ".nwave/config.json").write_text(
        json.dumps(
            {
                "documents": {
                    "discuss": {"destination": DISCUSS_DESTINATION},
                    "design": {"destination": DESIGN_DESTINATION},
                }
            }
        )
    )
    git(root, "add", ".")
    git(root, "commit", "-qm", "the reported defect")


def test_an_observed_defect_reaches_a_verified_correction_through_the_shared_producers(
    root: Path, step, turns: Path
) -> None:
    defective_repository(root)

    code, out, err = step(
        "discuss",
        "--repo-root",
        str(root),
        "--input",
        "-",
        stdin=json.dumps(discuss_payload()),
    )
    assert code == 0, out + err
    brief = (root / DISCUSS_DESTINATION).read_text()
    assert OBSERVED_DEFECT in brief and CORRECTED_OBSERVATION in brief

    code, out, err = step(
        "design",
        "--repo-root",
        str(root),
        "--value",
        "1",
        "--input",
        "-",
        stdin=json.dumps(design_payload()),
    )
    assert code == 0, out + err
    assert OBSERVED_DEFECT not in (root / DESIGN_DESTINATION).read_text()

    code, out, err = step(
        "distill",
        "--repo-root",
        str(root),
        "--input",
        "-",
        stdin=json.dumps(distill_payload()),
    )
    assert code == 0, out + err

    code, out, err = step(
        "oracle",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[authored_regression_oracle()],
    )
    assert code == 0, out + err
    assert ORACLE in block(out, err)["ORACLE-RED"]

    code, out, err = step(
        "craft",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[crafted_correction()],
    )
    assert code == 0, out + err

    code, out, err = step("verify", "--repo-root", str(root), answers=[])
    assert code == 0, out + err
    lines = block(out, err)
    assert lines["DELIVERY-OUTCOME"] == "Success"
    candidate = lines["CANDIDATE"]

    for role in ("reviewer", "examiner"):
        assert observed(root, step, role, candidate)["OUTCOME"] == "accepted"

    code, out, err = step(
        "integrate", "--repo-root", str(root), "--candidate", candidate
    )
    assert code == 0, out + err
    assert block(out, err)["DELIVERY-OUTCOME"] == "Success"
    assert (root / TARGET).read_text() == CORRECTED
    assert "nw-product-owner" not in asked(turns)


def test_the_published_bugfix_entry_step_composes_with_the_document_producers(
    root: Path, step, turns: Path
) -> None:
    """The route the published bugfix asset names, continued into the producers.

    `des po` is the entry the bugfix asset names and it constructs no durable
    authority of its own, so a fix that stops there has no conforming document.
    Continuing into the SAME producers a feature uses is what closes that, and
    it must not be refused as a second decomposition of somebody else's Request.
    """
    defective_repository(root)
    code, out, err = step(
        "po",
        "--repo-root",
        str(root),
        answers=[
            {
                "structured_output": {
                    "outcome": "accepted",
                    "diagnostic": "decomposed the reported defect",
                    "values": [{"observation": CORRECTED_OBSERVATION}],
                }
            }
        ],
        stdin=OBSERVED_DEFECT,
    )
    assert code == 0, out + err
    assert not (root / DISCUSS_DESTINATION).exists()

    code, out, err = step(
        "discuss",
        "--repo-root",
        str(root),
        "--input",
        "-",
        stdin=json.dumps(discuss_payload()),
    )
    assert code == 0, out + err
    assert OBSERVED_DEFECT in (root / DISCUSS_DESTINATION).read_text()
    assert asked(turns) == ["nw-product-owner"]


PUBLISHED_BUGFIX_ASSETS = (
    Path("nWave/skills/nw-bugfix/SKILL.md"),
    Path("nWave/tasks/nw/bugfix.md"),
)
SHARED_PRODUCERS = ("des discuss", "des design", "des devops", "des distill")
CHECKOUT = Path(__file__).parents[4]


def test_the_published_bugfix_assets_route_into_the_shared_document_producers() -> None:
    """The route a reader follows names the producers the walk above exercised.

    A published route that names only the entry step teaches a fix with no
    durable authority, which is the defect this scenario exists to keep closed.
    """
    for asset in PUBLISHED_BUGFIX_ASSETS:
        text = (CHECKOUT / asset).read_text()
        missing = [name for name in SHARED_PRODUCERS if name not in text]
        assert not missing, f"{asset} names no {missing}"
        assert "des oracle" in text
