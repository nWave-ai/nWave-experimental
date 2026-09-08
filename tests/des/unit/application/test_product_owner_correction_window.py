"""What a Product Owner turn may answer, and what the graph will consume.

WHAT THE RETIREMENT OF `des dispatch` CHANGED HERE, stated rather than quietly
dropped. Three scenarios drove `_product_owner_correction`, the DESIGN-to-PO
edge: the composer refused a design, computed the started prefix, and spent one
bounded turn asking for a replacement SUFFIX whose cardinality «may reduce or
retain, never increase» the not-yet-started slices. That edge is a fixed
correction the SOFTWARE traversed, so ADR-DES-003 Section 11 sorts it to the
composer and Section 13's ninth amendment retires it outright: «the software
traverses no correction edge; the orchestrator chooses the owner and re-invokes
it». Section 11 re-homes the turn itself -- «its prompt shape becomes the
Section 7 rewrite turn» -- and that turn asks for the WHOLE new sequence, so it
declares no window and the suffix-cardinality law has nothing left to bound.

ONE PROPERTY SURVIVES THAT, and it is stated below on one invocation: the
PRODUCER side, `extract_model_run`, still refuses an answer outside a declared
window at the boundary, before any consumer sees it. It is a law of the
envelope, not of the edge that used to declare the window.

WHAT DOES NOT SURVIVE, MEASURED AND NOT ASSUMED. The fourth scenario asserted
that a correction dropping values could not strand a preserved entry's
dependency -- reachable because the composer CONCATENATED a started prefix with
a model-supplied suffix, so the two halves could disagree about an edge. The
rewrite turn has no such seam: `ProductValue` carries an observation and
nothing else, and the graph's edges are derived from the order the Product
Owner returns, so a returned sequence cannot point outside itself. The
scenario is unreachable rather than untested, which is why it is recorded here
instead of being ported into a shape that would only look like it.

A NOTE FOR THE NEXT SLICE, not repaired here because it is outside this
retirement: with the edge gone, no production caller passes a non-`None`
`max_product_values`. The boundary law below therefore defends a parameter the
runtime no longer supplies. Removing the parameter or finding it a caller is a
decision for the owner of the adapter, not a side effect of retiring a command.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from des.adapters.driven.task_invocation.claude_code_task_adapter import (
    extract_model_run,
)
from des.adapters.driven.task_invocation.mocked_task_adapter import MockedTaskAdapter
from des.application.delivery_continuation import (
    DeliveryContinuationRunner,
    DeliveryOutcome,
)
from des.application.handover import (
    HandoverValue,
    StoredHandover,
    create_handover,
    load_handover,
)
from des.ports.driven_ports.task_invocation_port import (
    MalformedModelEnvelope,
    ModelOutcome,
    ModelRun,
)


REQUEST = "Deliver value\n"
CHANGED_REQUEST = "Deliver value, and say which index it read\n"
BOUND = "docs/product/architecture/brief.md#Value authority"


@given(
    window=st.integers(min_value=1, max_value=6),
    returned=st.integers(min_value=0, max_value=10),
)
@settings(max_examples=80, deadline=None)
def test_the_boundary_admits_exactly_the_window_and_refuses_the_rest(
    window: int, returned: int
) -> None:
    """The producer side of the closure, stated as one law.

    Whatever the provider actually sends, the turn crosses the port only when
    its cardinality is inside the declared window. Everything else raises, and
    a caller reports that as indeterminate rather than as a product refusal --
    a provider that breaks its own schema is never charged to the product.
    """
    stdout = json.dumps(
        {
            "structured_output": {
                "outcome": "accepted",
                "diagnostic": "",
                "values": [{"observation": f"v{index}"} for index in range(returned)],
            }
        }
    )
    inside = returned <= window

    if inside:
        run = extract_model_run(
            stdout, role_id="nw-product-owner", max_product_values=window
        )
        assert len(run.product_values) == returned
    else:
        with pytest.raises(MalformedModelEnvelope, match="ProductValuesOutsideWindow"):
            extract_model_run(
                stdout, role_id="nw-product-owner", max_product_values=window
            )


def test_a_rewrite_turn_declares_no_window_at_all(tmp_path: Path) -> None:
    """The falsifier for the paragraph above: the re-homed turn is unbounded.

    If a future slice re-introduced a suffix window on the rewrite, the
    cardinality law this file used to carry would be owed again -- and this
    assertion is what would say so, rather than the absence of a test nobody
    notices.
    """
    stored = create_handover(
        tmp_path,
        REQUEST,
        (
            HandoverValue(
                "the installed command reports outcome 0 to its caller", (), BOUND
            ),
        ),
    )
    assert isinstance(stored, StoredHandover)
    adapter = MockedTaskAdapter(
        predefined_result=ModelRun(ModelOutcome.Rejected, "not now", 0, False)
    )

    outcome = DeliveryContinuationRunner().rewrite_request(
        tmp_path, adapter, stored, CHANGED_REQUEST
    )

    assert isinstance(outcome, DeliveryOutcome)
    role, _, _, window, _ = adapter.invocations[0]
    assert (role, window) == ("nw-product-owner", None)
    # A refused rewrite writes nothing: the graph on disk is the one it read.
    persisted = load_handover(tmp_path, REQUEST)
    assert isinstance(persisted, StoredHandover)
    assert persisted.raw == stored.raw
