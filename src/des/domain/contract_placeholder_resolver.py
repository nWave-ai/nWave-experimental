"""The one literal placeholder token a compiled DeliveryContract SKELETON
carries for a semantic (value/judgment) field a mechanical compiler cannot
derive -- and the pure finder that later gates on it.

``des compile-contract`` writes this exact string into every ``nonEmptyText``
field ADR-SSOT-002 Section 4 names as ATD's own authorship duty
(``outcome``, each target's ``justification``, every ``boundary.*``
sub-field) instead of guessing prose. ``des validate-delivery-contract`` and
``des dispatch`` refuse a contract that still carries it, so an unfilled
skeleton can never reach DELIVER by accident.

Two DeliveryContract fields DESIGN also owns semantically (``paradigm``,
each target's ``contract-shape``) are schema ``enum``-typed and therefore
CANNOT represent this placeholder at all -- a free-text placeholder value
would itself fail schema validation. Those fields take an explicit,
overridable default at compile time instead (see
``des.application.compile_contract``); they are deliberately absent from
this module's fill-tracking, and are not a gap this resolver silently
ignores.
"""

from __future__ import annotations


PLACEHOLDER = "<ATD: fill>"

#: Free-text ``targetPlan`` fields that may legitimately carry
#: ``PLACEHOLDER`` -- every OTHER ``targetPlan`` field is either
#: mechanically derived (``candidate``/``decision``/``declared-imports``) or
#: enum-typed (``contract-shape``, see module docstring).
_TARGET_TEXT_FIELDS = ("justification",)
_BOUNDARY_TEXT_FIELDS = (
    "failure-behavior",
    "substrate-lie",
    "substrate-probe",
    "double-blind-spot",
)


def find_unfilled_placeholders(contract: dict) -> list[str]:
    """Every dotted field path inside ``contract`` still carrying the
    literal ``PLACEHOLDER`` string -- top-level ``outcome``, and every
    target's ``justification``/``boundary.*``. Order-stable (targets in
    dict-iteration order, matching the contract's own key order)."""
    findings: list[str] = []
    if contract.get("outcome") == PLACEHOLDER:
        findings.append("outcome")
    for target_path, target_plan in contract.get("targets", {}).items():
        for field in _TARGET_TEXT_FIELDS:
            if target_plan.get(field) == PLACEHOLDER:
                findings.append(f"targets.{target_path}.{field}")
        boundary = target_plan.get("boundary", {})
        for field in _BOUNDARY_TEXT_FIELDS:
            if boundary.get(field) == PLACEHOLDER:
                findings.append(f"targets.{target_path}.boundary.{field}")
    return findings
