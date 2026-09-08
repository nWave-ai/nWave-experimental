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

import sys
from pathlib import Path

from tests.des.acceptance.steps_for_the_orchestrator.conftest import block, git, nexts


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


def bind(root: Path, observation: str) -> None:
    """Bind one value's typed design facts, through the same boundary."""
    sys.path.insert(0, str(PACKAGE_PARENT))
    try:
        from des.application.handover import (
            HandoverValue,
            handover_path,
            read_handover,
            rewrite_handover,
        )
        from des.ports.driven_ports.task_invocation_port import (
            DesignFacts,
            DesignTarget,
        )

        raw = handover_path(root).read_bytes()
        stored = read_handover(raw)
        facts = DesignFacts(
            (DesignTarget("src/probe.py", "CREATE_NEW"),),
            "object_oriented",
            ("build it",),
            "tests/acceptance/test_probe.py",
            (),
            (("pytest", "tests/acceptance/test_probe.py"),),
        )
        rewritten = rewrite_handover(
            root,
            raw,
            stored.request,
            tuple(
                HandoverValue(
                    value.observation,
                    value.dependencies,
                    facts if value.observation == observation else value.authority,
                )
                for value in stored.values
            ),
        )
        assert not hasattr(rewritten, "what"), rewritten
    finally:
        sys.path.remove(str(PACKAGE_PARENT))


def record_oracle_turn(root: Path, request: str, observation: str) -> None:
    """Point the value's approved-oracle ref at a real commit, as the runner does."""
    sys.path.insert(0, str(PACKAGE_PARENT))
    try:
        from des.application.delivery_continuation import DeliveryContinuationRunner

        ref = DeliveryContinuationRunner._turn_ref(request, observation, "oracle")
    finally:
        sys.path.remove(str(PACKAGE_PARENT))
    git(root, "update-ref", ref, git(root, "rev-parse", "HEAD"))


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
    root: Path, step
) -> None:
    """The canonical next step is the FIRST one the state does not already hold."""
    decompose(root, REQUEST, "first observable value", "second observable value")
    unbound = nexts(step("state", "--repo-root", str(root))[1])
    assert unbound == [f"des design --repo-root {root} --value 1"]

    bind(root, "first observable value")
    bound = nexts(step("state", "--repo-root", str(root))[1])
    assert bound == [f"des oracle --repo-root {root} --value 1"]

    record_oracle_turn(root, REQUEST, "first observable value")
    with_oracle = nexts(step("state", "--repo-root", str(root))[1])
    assert with_oracle == [f"des craft --repo-root {root} --value 1"]


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
