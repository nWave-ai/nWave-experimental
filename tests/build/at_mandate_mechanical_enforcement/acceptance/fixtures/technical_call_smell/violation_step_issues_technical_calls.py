"""GOLDEN FIXTURE (planted violation — technical calls in step bodies) — M2 gate.

This file is NOT a real test. It is the recall-half corpus the slice-08 gate
scans: pytest-bdd step functions whose bodies issue TECHNICAL calls — an HTTP
client call (``requests.get``) and a DB call (``db.execute``) — where only
domain-language delegation belongs (the Mystery-Guest / Eager-Test smell family,
research C1; Mandate 2 test smells "``requests.post()`` in step method",
"``db.execute()`` in step method"). A step body that reaches for a transport or a
cursor is doing the system's work inline instead of delegating to a domain
service, so the scenario stops speaking the domain.

The M2 rule MUST flag it (``detect(...).flagged is True``), naming BOTH offending
steps with the technical callee each issues:

  * ``when_the_customer_submits_the_order`` issuing ``requests.post`` (HTTP), and
  * ``then_the_order_is_recorded`` issuing ``db.execute`` (DB).

A gate that cannot flag this planted violation is itself testing-theater
(ADR-TEST-002 D-E). The ``requests`` / ``db`` symbols are stand-in helpers so the
corpus parses; the gate reads structure (the dotted callee of each call site in a
step body), not behaviour.
"""

import requests  # stand-in HTTP client so the corpus parses.
from pytest_bdd import then, when


db = object()  # stand-in DB handle so the corpus parses.


@when("the customer submits the order")
def when_the_customer_submits_the_order(run_state):
    # VIOLATION: an HTTP transport call inside a step body — the step speaks the
    # wire, not the domain. Should delegate to a composition-root service.
    response = requests.post("https://shop.example/orders", json={"sku": "WIDGET"})
    run_state["response"] = response


@then("the order is recorded")
def then_the_order_is_recorded(run_state):
    # VIOLATION: a raw DB call inside a step body — the step reaches for a cursor
    # instead of asserting a domain outcome through the driving port.
    rows = db.execute("SELECT id FROM orders WHERE sku = 'WIDGET'")
    run_state["rows"] = rows
