"""A placeholder observation never becomes a persisted product value.

Run 20260906T005839Z-648259, turn 06.  The Product Owner correction window
answered ``{"outcome":"accepted","diagnostic":"test","values":[{"observation":
"a"}]}``.  The runner persisted "a" and then paid the architect ($0.55), the
acceptance designer ($0.34), its reviewer ($0.20) and a second designer before
the designer itself refused the byte: about $1.2 and 12 minutes for one
character.

The provider schema is the primary guard and lives in the adapter, where a
below-floor observation is unrepresentable before any turn is billed (GDP-0,
GDP-1).  This is the SECOND axis, and it exists for the same reason the
replacement window is re-stated at the envelope boundary: an envelope reaches
the runner without ever having passed the provider's validator whenever it is
replayed, hand-written, or produced by a double.  A turn that answers below the
floor established no semantic result, so it is indeterminate -- never a
delivery refusal charged to the product -- and nothing is written.
"""

from __future__ import annotations

from pathlib import Path

from des.adapters.driven.task_invocation.mocked_task_adapter import MockedTaskAdapter
from des.application.delivery_continuation import (
    DeliveryContinuationRunner,
    DeliveryOutcome,
)
from des.application.handover import (
    HandoverValue,
    StoredHandover,
    create_handover,
    handover_path,
    load_handover,
)
from des.ports.driven_ports.task_invocation_port import (
    ModelOutcome,
    ModelRun,
    ProductValue,
)


REQUEST = (
    "Make `des code-fact` say in its trace why the graphify provider did not "
    "answer, instead of leaving it out.\n"
)
#: The one byte the recorded turn answered.
PLACEHOLDER = "a"
PRESERVED = (
    "The trace of a query answered from the ast provider names graphify and the "
    "reason it did not answer, observed through the real command."
)
BOUND = "docs/product/architecture/brief.md#Value authority"


def _accepted_placeholder() -> ModelRun:
    """Turn 06, as a typed run: the shape a real provider produced that day."""
    return ModelRun(
        ModelOutcome.Accepted,
        "test",
        0,
        False,
        product_values=(ProductValue(PLACEHOLDER),),
    )


def test_the_decomposition_step_answering_a_placeholder_writes_no_handover(
    tmp_path: Path,
) -> None:
    """No graph is created, and the one turn this step buys is the only cost.

    MIGRATED. This drove `_run_locked`, which walked from the PO turn into
    design; that composer is retired, so the observation is stated on the step
    that owns it. The assertion it used to need -- «no role downstream of the PO
    is ever asked» -- is now true by construction, because `decompose` asks for
    one turn and returns. What remains falsifiable, and is asserted, is that
    nothing is WRITTEN.
    """
    adapter = MockedTaskAdapter(predefined_result=_accepted_placeholder())

    outcome = DeliveryContinuationRunner(adapter).decompose(tmp_path, adapter, REQUEST)

    assert isinstance(outcome, DeliveryOutcome)
    assert outcome.failure is not None
    assert outcome.failure.what == "ProductValuePlaceholder"
    assert [role for role, *_ in adapter.invocations] == ["nw-product-owner"]
    assert not handover_path(tmp_path).exists()


def test_a_rewrite_answering_a_placeholder_leaves_the_graph_untouched(
    tmp_path: Path,
) -> None:
    """The second Product Owner turn: the stored graph survives the placeholder.

    MIGRATED from the DESIGN-to-PO correction edge, which ADR-DES-003 Section 11
    re-homes: «its prompt shape becomes the Section 7 rewrite turn; the edge
    itself is a `NEXT` the orchestrator may take». The floor holds on that turn
    too, and the same byte still buys nothing.
    """
    stored = create_handover(
        tmp_path,
        REQUEST,
        (
            HandoverValue(PRESERVED, (), BOUND),
            HandoverValue("the trace names the stale index", (PRESERVED,), None),
        ),
    )
    assert isinstance(stored, StoredHandover)
    adapter = MockedTaskAdapter(predefined_result=_accepted_placeholder())

    outcome = DeliveryContinuationRunner().rewrite_request(
        tmp_path, adapter, stored, REQUEST + "and say which index it read.\n"
    )

    assert isinstance(outcome, DeliveryOutcome)
    assert outcome.failure is not None
    assert outcome.failure.what == "ProductValuePlaceholder"
    assert adapter.invocation_count == 1
    persisted = load_handover(tmp_path, REQUEST)
    assert isinstance(persisted, StoredHandover)
    assert persisted.raw == stored.raw


def test_the_failure_states_what_why_and_how(tmp_path: Path) -> None:
    """A rejection that lies is worse than a bare traceback: it names the byte."""
    adapter = MockedTaskAdapter(predefined_result=_accepted_placeholder())

    outcome = DeliveryContinuationRunner(adapter).decompose(tmp_path, adapter, REQUEST)

    assert isinstance(outcome, DeliveryOutcome)
    assert outcome.failure is not None
    assert "1 character" in outcome.failure.why
    assert outcome.failure.how
