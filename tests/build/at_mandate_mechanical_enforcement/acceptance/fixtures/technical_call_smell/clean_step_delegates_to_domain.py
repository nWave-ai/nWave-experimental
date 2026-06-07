"""GOLDEN FIXTURE (clean corpus — domain-delegating steps) — M2 gate.

This file is NOT a real test. It is the precision-half corpus the slice-08 gate
scans: a well-formed step suite the M2 rule MUST NOT flag
(``detect(...).flagged is False``). It is the false-positive guard the slice-08
learning hypothesis demands (feature-delta 335): a denylist whose false-positive
rate on legitimate domain-delegating steps is too high is disproved. Every step
here DELEGATES to a domain-language service and asserts on a domain outcome — no
HTTP client, no cursor, no status-code assertion.

It carries the precision near-misses a naive denylist would over-fire on:

  1. A domain delegation whose method happens to be ``execute`` on a DOMAIN
     object (``the_gate.judge(...)`` / ``order_service.place(...)``) — the
     denylist keys on the dotted callee of a TECHNICAL handle
     (``db.execute`` / ``cursor.execute`` / ``session.execute`` /
     ``requests.*`` / ``httpx.*``), NEVER on a bare ``.place`` / ``.judge`` on a
     domain service. A domain method must not be confused with a DB cursor call.

  2. A ``.status`` attribute READ on a domain result
     (``assert outcome.status is Confirmed``) — a domain-outcome assertion, not a
     transport ``status_code`` driven by an HTTP call. No call site, no breach.

The gate must approach 100% precision: flagging any of these would block a commit
on a clean domain-delegating step (the slice-08 learning-hypothesis failure).
The ``order_service`` / ``the_gate`` / ``Confirmed`` symbols are stand-in domain
helpers so the corpus parses; the gate reads structure (the dotted callee of each
call site in a step body), not behaviour.
"""

from pytest_bdd import then, when


order_service = object()  # stand-in domain service so the corpus parses.
the_gate = object()  # stand-in domain service so the corpus parses.
Confirmed = object()  # stand-in domain outcome so the corpus parses.


@when("the customer submits the order")
def when_the_customer_submits_the_order(run_state):
    # CLEAN: delegates to a domain service via the driving port. ``.place`` is a
    # domain method, not a DB cursor / HTTP call — outside the denylist.
    run_state["outcome"] = order_service.place(run_state["cart"])


@when("the gate judges the change")
def when_the_gate_judges_the_change(run_state):
    # CLEAN: delegates to a domain service. ``.judge`` is domain language.
    run_state["verdict"] = the_gate.judge(run_state["change"])


@then("the order is confirmed")
def then_the_order_is_confirmed(run_state):
    # CLEAN precision near-miss: asserts a DOMAIN outcome status — a bare
    # attribute read on a domain result, NOT a transport status_code driven by an
    # HTTP call. No call site in the assert → no breach.
    assert run_state["outcome"].status is Confirmed
