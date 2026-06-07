"""GOLDEN FIXTURE (frozen conformant snapshot) — slice-12 drift-guard precision corpus.

This is NOT the live testarch substrate; it is the PRECISION-half (clean) corpus
for the slice-12 drift-guard conformance gate (ADR-TEST-002 D-E golden-fixture
meta-rule). It is a FROZEN snapshot that is DRIFT-FREE in BOTH facets, so the gate
clears it — proving the gate does NOT over-fire (the precision half):

  * Layer-value conformant — every layer value a classification set references IS
    in the (fixture) producible-layer surface. The gate MUST report CONFORMANT
    (zero layer-value violations).
  * Capability conformant — every registered capability IS in the (fixture) adapter
    method-name surface. The gate MUST report CONFORMANT (zero capability
    violations).

The clean snapshot is the frozen-clean complement of the violation snapshot: the
violation fixture proves the gate CAN bite (recall), this proves the gate does NOT
bite a conformant substrate (precision). A gate that flagged this clean snapshot
would be a false-positive that blocks a commit — the fail-closed bar this fixture
guards. The live-substrate precision scenario is the production-surface analogue;
this frozen-clean fixture is the convention-required ``clean_*`` golden complement
(the slice-11 Tier-M meta-gate requires every shipped gate to carry BOTH a
``violation_*`` and a ``clean_*`` fixture).
"""

from __future__ import annotations


# --- Layer-value-coverage conformant snapshot ------------------------------

# Classification sets whose every referenced layer value IS producible by the
# (fixture) adapter. Keyed by rule-set name → referenced layer values.
CONFORMANT_CLASSIFICATION_SETS: dict[str, frozenset[str]] = {
    "fixture.PLANTED_FORBIDDEN_LAYERS": frozenset({"integration", "wiring_e2e", "e2e"}),
    "fixture.PLANTED_AUDITED_LAYERS": frozenset({"unit", "in_memory_acceptance"}),
}

# The (fixture) producible-layer surface — a superset of every referenced value, so
# the gate finds zero non-producible references.
CONFORMANT_PRODUCIBLE_LAYERS: frozenset[str] = frozenset(
    {"unit", "in_memory_acceptance", "integration", "wiring_e2e", "e2e", "unknown"}
)


# --- Real-adapter capability-conformance conformant snapshot ---------------

# Registered capabilities whose every member IS realized on the (fixture) adapter.
CONFORMANT_REGISTERED_CAPABILITIES: frozenset[str] = frozenset(
    {"functions_with_decorator", "imports_in_function", "calls_in_function"}
)

# The (fixture) adapter method-name surface — a superset of every registered
# capability, so the gate finds zero unrealized capabilities.
CONFORMANT_ADAPTER_METHOD_NAMES: frozenset[str] = frozenset(
    {
        "functions_with_decorator",
        "imports_in_function",
        "calls_in_function",
        "layer_of_file",
    }
)
