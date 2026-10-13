"""Public oracle: `des state`, the projection every other step is read against.

ADR-SSOT-002 Section 4b names a step by PROPERTY -- «Reading the owned state as
a projection: takes the repository root, returns the exact Request, the ordered
values, what each already carries».  It is the step an orchestrator invokes
after every terminal, so its whole contract is that it READS: it writes no byte,
it invokes no role, and it EXECUTES NOTHING that its own `NEXT` line names
(Section 4b, «no step executes what its own `NEXT` names»).

Every scenario drives the real `des` CLI as a real subprocess against a real
temporary Git repository, because that is exactly how the orchestrator reaches
it.  The handover bytes are written by the software's own `create_handover`
boundary rather than by hand, so no scenario asserts against a shape the code
does not actually persist.
"""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    accepted_values,
    block,
    git,
    nexts,
)


PACKAGE_PARENT = Path(__file__).parents[4] / "src"

REQUEST = "the projection names the exact Request it was decomposed from"


def decompose(root: Path, request: str, *observations: str) -> None:
    """Persist one decomposition through the software's own write boundary."""
    sys.path.insert(0, str(PACKAGE_PARENT))
    try:
        from des.application.handover import HandoverValue, create_handover

        values = tuple(
            HandoverValue(observation, tuple(observations[:index]), None)
            for index, observation in enumerate(observations)
        )
        stored = create_handover(root, request, values)
        assert not hasattr(stored, "what"), stored
    finally:
        sys.path.remove(str(PACKAGE_PARENT))


ORACLE = "tests/acceptance/test_value.py"
SUPPORT = "tests/acceptance/support.py"


from tests.des._helpers.host_facts import design_manifest
from tests.des.acceptance.steps_for_the_orchestrator.conftest import observation


def design_answer() -> dict:
    return {
        "structured_output": {
            "outcome": "accepted",
            "diagnostic": "bound the value to its typed design facts",
            "manifest": design_manifest(
                {
                    "targets": [
                        {"path": "src/product/value.py", "decision": "CREATE_NEW"}
                    ],
                    "paradigm": "object_oriented",
                    "decisions": ["one opaque semantic decision"],
                    "oracle": ORACLE,
                    "acceptance_supports": [SUPPORT],
                    "verification": [[sys.executable, "-m", "pytest", ORACLE]],
                    "oracle_verification_index": 0,
                    "architectural_tests": {
                        "applicability": "not_applicable",
                        "reason": "The fixture has no structural boundary change.",
                    },
                    "contract_tests": {
                        "applicability": "not_applicable",
                        "reason": "The fixture changes no shared contract.",
                    },
                    "prefactoring": {
                        "applicability": "not_applicable",
                        "reason": "The fixture requires no preservation move.",
                    },
                    "agreement_analysis": {
                        "applicability": "not_applicable",
                        "reason": "The fixture has no affected agreement.",
                    },
                    "reuse_analysis": {"candidates": []},
                    "impact_closure": {
                        "applicability": "not_applicable",
                        "reason": "The fixture reaches no public surface, consumer or build metadata.",
                    },
                },
                observation("A"),
                1,
            ),
        }
    }


def oracle_answer() -> dict:
    return {
        "structured_output": {"outcome": "accepted", "diagnostic": "authored"},
        "writes": {
            ORACLE: "def test_value():\n    import product.value  # noqa\n",
            SUPPORT: "MARKER = 1\n",
        },
    }


def test_an_undecomposed_root_projects_no_request_and_names_the_product_owner(
    root: Path, step, turns: Path
) -> None:
    """Nothing started is a state the projection READS, never an error."""
    code, out, err = step("state", "--repo-root", str(root))
    assert code == 0, err
    lines = block(out, err)
    assert lines["DELIVERY-OUTCOME"] == "Success"
    assert lines["REQUEST"] == "(none)"
    assert nexts(out)[0].startswith(f"des po --repo-root {root}")
    assert "HOW-TO-INVOKE" in lines
    assert not turns.exists()


def test_the_projection_carries_the_exact_request_and_its_ordered_values(
    root: Path, step
) -> None:
    decompose(root, REQUEST, "first observable value", "second observable value")
    code, out, err = step("state", "--repo-root", str(root))
    assert code == 0, err
    lines = block(out, err)
    assert lines["DELIVERY-OUTCOME"] == "Success"
    assert REQUEST in lines["REQUEST"]
    assert "first observable value" in out
    assert "second observable value" in out
    assert "VALUE-1" in lines
    assert "VALUE-2" in lines


def test_the_next_step_is_derived_from_what_the_state_already_carries(
    root: Path, step, turns: Path
) -> None:
    """The canonical next step is the FIRST one the state does not already hold."""
    code, out, err = step(
        "po",
        "--project",
        "--repo-root",
        str(root),
        answers=[accepted_values("A", "B")],
        stdin=REQUEST,
    )
    assert code == 0, out + err
    unbound = nexts(step("state", "--repo-root", str(root))[1])
    assert [shlex.split(advice)[1] for advice in unbound] == ["design"]

    code, out, err = step(
        "design", "--repo-root", str(root), "--value", "1", answers=[design_answer()]
    )
    assert code == 0, out + err
    bound = nexts(step("state", "--repo-root", str(root))[1])
    assert [shlex.split(advice)[1] for advice in bound] == ["oracle"]

    code, out, err = step(
        "oracle", "--repo-root", str(root), "--value", "1", answers=[oracle_answer()]
    )
    assert code == 0, out + err
    with_oracle = nexts(step("state", "--repo-root", str(root))[1])
    assert [shlex.split(advice)[1] for advice in with_oracle] == ["craft"]


def test_the_projection_writes_nothing_and_runs_no_step_it_names(
    root: Path, step, turns: Path
) -> None:
    """Section 4b: a step names the next step as DATA and executes none of it."""
    decompose(root, REQUEST, "first observable value")
    before = (root / ".nwave" / "des" / "handover.json").read_bytes()
    refs_before = git(root, "for-each-ref", "--format=%(refname)")
    head_before = git(root, "rev-parse", "HEAD")
    status_before = git(root, "status", "--porcelain")

    code, _out, err = step("state", "--repo-root", str(root))

    assert code == 0, err
    assert (root / ".nwave" / "des" / "handover.json").read_bytes() == before
    assert git(root, "for-each-ref", "--format=%(refname)") == refs_before
    assert git(root, "rev-parse", "HEAD") == head_before
    assert git(root, "status", "--porcelain") == status_before
    assert not turns.exists()


def test_an_unreadable_root_refuses_without_pretending_to_have_read_it(
    tmp_path: Path, step
) -> None:
    absent = tmp_path / "not-a-repository"
    code, out, err = step("state", "--repo-root", str(absent))
    assert code == 1
    lines = block(out, err)
    assert lines["DELIVERY-OUTCOME"] == "Refusal"
    assert lines["WHAT"] == "InvalidRepositoryRoot"
    assert "HOW" in lines
