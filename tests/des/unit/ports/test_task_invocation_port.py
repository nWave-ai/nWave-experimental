"""Observable behavior of the in-repository :class:`TaskInvocationPort` double.

The port carries the evolved keyword-only
``invoke(role_id, prompt, cwd, max_product_values)`` and returns
:class:`ModelRun` data -- including a failed retry-unsafe turn -- so a
test observing the double is observing a shape production can actually produce.
"""

from __future__ import annotations

from pathlib import Path

from des.adapters.driven.task_invocation.mocked_task_adapter import MockedTaskAdapter
from des.ports.driven_ports.task_invocation_port import ModelOutcome, ModelRun


def test_scripted_queue_is_returned_in_order_then_falls_back_to_the_default() -> None:
    failed = ModelRun(ModelOutcome.Indeterminate, "timed out", 124, False)
    adapter = MockedTaskAdapter(
        results_queue=[
            ModelRun(ModelOutcome.Accepted, "", 0, False),
            failed,
        ],
        predefined_result=ModelRun(ModelOutcome.Rejected, "", 0, False),
    )
    root = Path("/repo")

    first = adapter.invoke(role_id="crafter", prompt="p1", cwd=root)
    second = adapter.invoke(role_id="examiner", prompt="p2", cwd=root)
    third = adapter.invoke(role_id="crafter", prompt="p3", cwd=root)

    assert first.outcome is ModelOutcome.Accepted
    # A failed turn crosses the port as DATA, never as a silent empty success.
    assert (
        second.outcome,
        second.diagnostic,
        second.exit_status,
        second.retry_safe,
    ) == (
        ModelOutcome.Indeterminate,
        "timed out",
        124,
        False,
    )
    assert third.outcome is ModelOutcome.Rejected
    assert adapter.results_queue == []


def test_every_invocation_records_the_request_that_asked_for_it() -> None:
    adapter = MockedTaskAdapter()

    adapter.invoke(role_id="crafter", prompt="implement", cwd=Path("/repo/lane-a"))
    adapter.invoke(
        role_id="reviewer",
        prompt="review",
        cwd=Path("/repo/lane-b"),
        max_product_values=2,
        defect_values=("one value",),
    )

    assert adapter.invocation_count == 2
    assert adapter.invocations == [
        ("crafter", "implement", Path("/repo/lane-a"), None, ()),
        ("reviewer", "review", Path("/repo/lane-b"), 2, ("one value",)),
    ]


def test_unscripted_adapter_returns_a_neutral_successful_run() -> None:
    run = MockedTaskAdapter().invoke(role_id="crafter", prompt="p", cwd=Path())

    assert run == ModelRun(ModelOutcome.Accepted, "", 0, False)
