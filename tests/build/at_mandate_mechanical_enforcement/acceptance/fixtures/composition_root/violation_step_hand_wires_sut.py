"""GOLDEN FIXTURE (planted violation — hand-wired SUT in a step body) — P3 gate.

This file is NOT a real test. It is the recall-half corpus the slice-09 gate
scans: a pytest-bdd step body that HAND-WIRES the system-under-test — it
assembles the SUT's collaborator object graph inline (``repo = InMemoryRepo()``;
``clock = FakeClock()``; ``service = OrderService(repo, clock)``) instead of
reaching a production composition-root entry call (``build_application()`` /
``compose_root()``). A hand-wired step duplicates the production wiring, drifts
from it, and exercises an object graph the user never runs (Pillar 3, "app as in
production"; the SUT is built via the production composition root, only
external/non-deterministic ports are faked).

The P3 rule MUST flag it (``detect(...).flagged is True``), naming the offending
step with the SUT-collaborator type it hand-wires:

  * ``when_the_customer_submits_the_order`` constructing ``OrderService`` (the
    application service) — the deepest collaborator the step assembles by hand.

A gate that cannot flag this planted violation is itself testing-theater
(ADR-TEST-002 D-E). The ``InMemoryRepo`` / ``FakeClock`` / ``OrderService``
symbols are stand-in collaborator types so the corpus parses; the gate reads
structure (the constructed-type of each assignment in a step body, cross-checked
against the absence of a composition-root entry call), not behaviour.
"""

from pytest_bdd import then, when


class InMemoryRepo:  # stand-in SUT collaborator so the corpus parses.
    pass


class FakeClock:  # stand-in SUT collaborator so the corpus parses.
    pass


class OrderService:  # stand-in SUT (application service) so the corpus parses.
    def __init__(self, repo, clock):
        self._repo = repo
        self._clock = clock

    def place(self, cart):
        return cart


@when("the customer submits the order")
def when_the_customer_submits_the_order(run_state):
    # VIOLATION: the step hand-wires the SUT's collaborator object graph inline —
    # a repository, a clock, and the application service — instead of reaching a
    # production composition-root entry call. This wiring duplicates and drifts
    # from production; the user never runs this object graph.
    repo = InMemoryRepo()
    clock = FakeClock()
    service = OrderService(repo, clock)
    run_state["outcome"] = service.place(run_state["cart"])


@then("the order is confirmed")
def then_the_order_is_confirmed(run_state):
    # CLEAN here — a bare domain-outcome read, no construction. The breach above is
    # what the gate flags; this Then carries no SUT construction.
    assert run_state["outcome"] is not None
