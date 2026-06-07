"""GOLDEN FIXTURE (planted violation — technical assertion) — M2 gate.

This file is NOT a real test. It is the second recall-half corpus the slice-08
gate scans: a step body whose assertion is DRIVEN BY a technical call — an HTTP
client call issued inside the ``assert`` so the step asserts on a status code
(``assert client.get(url).status_code == 200``). This is the "Technical
assertions" denylist family of Mandate 2 ("``assert response.status_code``"): the
step asserts a transport-level fact, not a domain outcome.

The adapter-producible mechanism is the DOTTED CALLEE of the call site — the
denylisted ``requests.get`` HTTP call appears inside the ``assert`` and
``ast.walk`` over the step body reaches it (a bare attribute read with NO call,
e.g. ``assert response.status_code == 201`` with ``response`` already in hand,
carries no call site and is outside the dotted-callee mechanism — see the
slice-08 [REF] residue note).

The M2 rule MUST flag it (``detect(...).flagged is True``), naming the offending
step ``then_the_response_is_ok`` with the technical callee ``requests.get``.

A gate that cannot flag this planted violation is itself testing-theater
(ADR-TEST-002 D-E). The ``requests`` symbol is a stand-in helper so the corpus
parses; the gate reads structure (the dotted callee inside the assert), not
behaviour.
"""

import requests  # stand-in HTTP client so the corpus parses.
from pytest_bdd import then


@then("the response is ok")
def then_the_response_is_ok(run_state):
    # VIOLATION: the assertion is driven by an HTTP transport call — the step
    # asserts a status code (a wire fact), not a domain outcome.
    assert requests.get("https://shop.example/orders/1").status_code == 200
