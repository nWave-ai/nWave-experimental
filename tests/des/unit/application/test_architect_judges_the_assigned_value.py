"""The architect judges the value it was assigned, never the whole Request.

The Product Owner decomposes the Request once and software persists the ordered
value graph.  Every later role works on ONE entry of that graph.  Which entry is
under judgement is a matter of FORM, and
``boundary:software-measures-model-decides`` puts form in the software: the
runner constructs the turn, so it must make "the decomposition already happened
and your unit is this value" a fact the model READS, not one it has to infer.

Measured on 2026-09-04 (``defects.md``, row
``architect-receives-raw-request-and-reslices-upstream-decomposition``): the
runner sent ``request`` first and the assigned ``observation`` second, with no
graph.  The architect re-derived the decomposition from the raw text, found two
values in it, and returned ``rejected`` with "Request bundles two values" while
conceding that the one observation it received was a well-formed slice.  Nothing
in that turn was a semantic error, so the refusal was billed to the model for the
software's own omission.

These are laws about prompt COMPOSITION, which is why the double records what was
asked rather than what came back.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

import pytest

from des.adapters.driven.task_invocation.mocked_task_adapter import MockedTaskAdapter
from des.application.delivery_continuation import DeliveryContinuationRunner
from des.application.handover import HandoverValue, StoredHandover, create_handover
from des.ports.driven_ports.task_invocation_port import ModelOutcome, ModelRun
from tests.des._helpers.step_stimulus import StepRefused, designed


REQUEST = (
    "Two observed defects. 1. the code-fact query answers an empty caller set at "
    "binding-resolved confidence. 2. the release guardians import a stale scripts "
    "package under uv run.\n"
)
FIRST = "the code-fact query no longer answers an empty caller set as verified"
SECOND = "the release guardians import the repository's own scripts package"


def _facts(prompt: str) -> dict[str, object]:
    """The prompt read back as the ordered JSON facts the composer emitted."""
    pairs = [line.split(": ", 1) for line in prompt.splitlines()]
    return {key: json.loads(value) for key, value in pairs}


def _two_value_graph(root: Path) -> StoredHandover:
    stored = create_handover(
        root,
        REQUEST,
        (
            HandoverValue(FIRST, (), None),
            HandoverValue(SECOND, (FIRST,), None),
        ),
    )
    assert isinstance(stored, StoredHandover)
    return stored


@pytest.fixture
def architect_turn(tmp_path) -> tuple[str, str, dict[str, object]]:
    """The DESIGN turn the runner issues for the first value of the graph.

    The stimulus invokes that ONE step by name, so what is asserted below is the
    prompt `design_value` composes and nothing a sequencer chose around it.  The
    scripted refusal keeps the turn to a single invocation; whether the step then
    binds or refuses is not this file's claim, so `StepRefused` is let pass.
    """
    stored = _two_value_graph(tmp_path)
    adapter = MockedTaskAdapter(
        predefined_result=ModelRun(ModelOutcome.Rejected, "", 0, False)
    )

    runner = DeliveryContinuationRunner(adapter)
    with contextlib.suppress(StepRefused):
        designed(runner, adapter, tmp_path, stored)

    role, prompt, _, _, _ = adapter.invocations[0]
    return role, prompt, _facts(prompt)


def test_the_assigned_value_is_the_first_fact_the_architect_reads(
    architect_turn,
) -> None:
    role, _, facts = architect_turn

    assert role == "nw-solution-architect"
    assert next(iter(facts)) == "observation"
    assert facts["observation"] == FIRST


def test_the_architect_reads_the_settled_decomposition_of_the_whole_request(
    architect_turn,
) -> None:
    """The sibling value is visible as a SEPARATE entry, dependencies included.

    This is the fact whose absence caused the measured refusal: seeing the graph,
    the model can read that the second value is already someone else's turn.
    """
    _, _, facts = architect_turn

    assert facts["decomposition"] == [[FIRST, []], [SECOND, [FIRST]]]


def test_the_raw_request_text_is_not_the_object_of_the_architect_s_judgement(
    architect_turn,
) -> None:
    """Only the Product Owner receives the Request; it decomposed it once."""
    _, prompt, facts = architect_turn

    assert "request" not in facts
    assert "Two observed defects" not in prompt


def test_the_root_is_declared_after_the_assigned_value_never_before_it(
    architect_turn, tmp_path
) -> None:
    """The runner's own fact, placed where it cannot displace the value.

    The root is what the model needs to resolve any path it is given, and only
    the runner knows it; but the first thing the architect must read is still
    the value it was assigned, so the fact is APPENDED.
    """
    _, _, facts = architect_turn

    assert next(iter(facts)) == "observation"
    assert facts["repository_root"] == str(tmp_path)
    assert Path(facts["repository_root"]).is_absolute()  # type: ignore[arg-type]
    assert "repository_root" in facts["path_convention"]  # type: ignore[operator]
