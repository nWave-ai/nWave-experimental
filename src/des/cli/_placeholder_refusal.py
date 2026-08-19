"""Shared unfilled-placeholder refusal -- mirrors the other five
``des dispatch``/``des validate-delivery-contract`` shared refusal modules
(``_declared_import_refusal.py`` et al.) exactly: one WHAT/WHY/HOW per
finding, no drifting second copy across the two point-of-use verification
call sites (ADR-SSOT-002 Section 4a item 9).
"""

from __future__ import annotations

from des.domain.contract_placeholder_resolver import (
    PLACEHOLDER,
    find_unfilled_placeholders,
)


def all_unfilled_placeholder_findings(contract: dict) -> list[tuple[str, str, str]]:
    """One ``(what, why, how)`` per field still carrying the literal
    ``des compile-contract`` skeleton placeholder."""
    return [
        (
            f"{field_path} still carries the compiler's literal placeholder "
            f"{PLACEHOLDER!r}",
            "a compiled skeleton leaves every semantic/value-judgment field "
            "as an explicit placeholder rather than a guess; DELIVER cannot "
            "trust a contract that was never actually authored",
            f"replace {field_path} with ATD's own real value-side prose "
            "before this contract is dispatchable",
        )
        for field_path in find_unfilled_placeholders(contract)
    ]


def first_unfilled_placeholder_finding(contract: dict) -> tuple[str, str, str] | None:
    return next(iter(all_unfilled_placeholder_findings(contract)), None)
