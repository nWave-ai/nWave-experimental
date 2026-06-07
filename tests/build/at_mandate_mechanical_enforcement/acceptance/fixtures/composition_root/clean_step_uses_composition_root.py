"""GOLDEN FIXTURE (clean corpus — composition-root step suite) — P3 gate.

This file is NOT a real test. It is the precision-half corpus the slice-09 gate
scans: a well-formed step suite the P3 rule MUST NOT flag
(``detect(...).flagged is False``). It is the false-positive guard the slice-09
learning hypothesis demands (feature-delta): if "hand-wired SUT" cannot be
distinguished structurally from a legitimate composition-root call, P3 is not the
AST-tractable Pillar the research claims. Every step here builds the SUT through a
production composition-root entry call (``build_application()``) and drives it —
no inline collaborator object-graph assembly.

It carries the precision near-misses a naive rule would over-fire on:

  1. A DOMAIN VALUE-OBJECT construction that is NOT a SUT collaborator
     (``money = Money(150)``) — the rule keys on the construction of a known
     SUT-COLLABORATOR type (``InMemoryRepo`` / ``FakeClock`` / ``OrderService``),
     NEVER on a value object the step legitimately builds to drive the composed
     app. A value-object construction must not be confused with hand-wiring the
     application's object graph.

  2. An ATTRIBUTE READ on the composed app (``app.order_service.place(...)``) — a
     call THROUGH the composition root, not an inline construction of a
     collaborator. No collaborator-constructing assignment, no breach.

The gate must approach 100% precision: flagging any of these would block a commit
on a clean composition-root step (the slice-09 learning-hypothesis failure). The
``build_application`` / ``Money`` symbols are stand-in helpers so the corpus
parses; the gate reads structure (the constructed-type of each assignment in a
step body, cross-checked against the presence of a composition-root entry call),
not behaviour.
"""

from pytest_bdd import then, when


def build_application():  # stand-in composition-root entry so the corpus parses.
    return object()


class Money:  # stand-in domain VALUE OBJECT (not a SUT collaborator) so it parses.
    def __init__(self, amount):
        self.amount = amount


@when("the customer submits the order")
def when_the_customer_submits_the_order(run_state):
    # CLEAN: builds the SUT through the production composition-root entry call, then
    # drives it. No inline collaborator object-graph assembly — the wiring is the
    # production one, not a hand-built copy.
    app = build_application()
    run_state["app"] = app


@when("the order total is computed")
def when_the_order_total_is_computed(run_state):
    # CLEAN precision near-miss #1: constructs a DOMAIN VALUE OBJECT (``Money``) to
    # drive the composed app. A value object is NOT a SUT collaborator — building
    # one is not hand-wiring the application. Outside the collaborator-type set.
    money = Money(150)
    run_state["total"] = money


@then("the order is confirmed")
def then_the_order_is_confirmed(run_state):
    # CLEAN precision near-miss #2: drives the SUT THROUGH the composed app — an
    # attribute read + call on ``app``, not an inline construction of a
    # collaborator. No collaborator-constructing assignment → no breach.
    app = run_state["app"]
    run_state["outcome"] = app.order_service.place(run_state["cart"])
