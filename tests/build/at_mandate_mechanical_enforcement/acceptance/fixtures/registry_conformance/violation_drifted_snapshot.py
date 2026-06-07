"""GOLDEN FIXTURE (frozen drifted snapshot) — slice-12 drift-guard recall corpus.

This is NOT the live testarch substrate; it is the RECALL-half corpus for the
slice-12 drift-guard conformance gate (ADR-TEST-002 D-E golden-fixture meta-rule).
It is a FROZEN snapshot that PERMANENTLY carries BOTH drift facets, so the gate's
recall scenario stays GREEN forever (the live substrate is cleaned by A_GREEN; this
fixture is never cleaned — it is the perpetual witness that the gate CAN bite):

  * Layer-value drift — a classification set referencing a bogus layer value
    (``ghost_layer``) that the (fixture) producible-layer surface does not contain.
    The gate MUST flag it and name the bogus value.
  * Capability drift — a registered capability (``ghost_capability``) that the
    (fixture) adapter method-name surface does not contain. The gate MUST flag it
    and name the unrealized capability.

A gate that cannot detect this planted drift is itself testing-theater — the very
disease it exists to detect one level down. The values are deliberately bogus
(``ghost_*``) so the recall fixture can never accidentally coincide with a real
``Layer.value`` / ``Capability.value`` and drift into a false negative when the
real vocabulary evolves.
"""

from __future__ import annotations


# --- Layer-value-coverage recall snapshot ----------------------------------

# A classification set referencing a layer value the (fixture) adapter cannot
# produce. Keyed by rule-set name → referenced layer values.
DRIFTED_CLASSIFICATION_SETS: dict[str, frozenset[str]] = {
    "fixture.PLANTED_FORBIDDEN_LAYERS": frozenset({"unit", "ghost_layer"}),
}

# The (fixture) producible-layer surface — what the fixture adapter "can emit".
# ``ghost_layer`` is deliberately ABSENT so the referenced value is non-producible.
DRIFTED_PRODUCIBLE_LAYERS: frozenset[str] = frozenset(
    {"unit", "in_memory_acceptance", "integration", "wiring_e2e", "e2e", "unknown"}
)

# The exact non-producible layer value the gate MUST name (recall assertion).
PLANTED_NON_PRODUCIBLE_LAYER_VALUE: str = "ghost_layer"


# --- Real-adapter capability-conformance recall snapshot -------------------

# The (fixture) registered capabilities — includes one registered-but-unrealized
# member (``ghost_capability``) the fixture adapter does not implement.
DRIFTED_REGISTERED_CAPABILITIES: frozenset[str] = frozenset(
    {"functions_with_decorator", "imports_in_function", "ghost_capability"}
)

# The (fixture) adapter method-name surface — ``ghost_capability`` is deliberately
# ABSENT so the registered capability is unrealized on the (fixture) adapter.
DRIFTED_ADAPTER_METHOD_NAMES: frozenset[str] = frozenset(
    {"functions_with_decorator", "imports_in_function"}
)

# The exact unrealized capability the gate MUST name (recall assertion).
PLANTED_UNREALIZED_CAPABILITY: str = "ghost_capability"
