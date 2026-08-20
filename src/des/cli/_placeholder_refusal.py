"""Shared unfilled-placeholder refusal -- mirrors the other shared refusal
modules' shape exactly: one WHAT/WHY/HOW per finding, no drifting second
copy across the two point-of-use verification call sites (`des dispatch`
and `des validate-delivery-contract`, ADR-SSOT-002 Section 4a item 9). The
one placeholder check both still run directly -- unlike the three
declared-imports/verification-path/EXTEND-citation checks Ale's
construction-over-file correction (2026-08-20, "the contract has one
writer -- `des fill-contract` is the constructor") deleted, an unfilled
`<ATD: fill>` leaf is not something construction can rule out: `des
fill-contract` refuses to WRITE one (a value equal to the literal
placeholder is itself a refused fill), but nothing stops a contract
reaching either call site without ever having gone through `des
fill-contract` at all (a hand-authored one, or the same condition the
Agda vacuity report names: "a hand-typed contract... gets NONE of this
protection" -- ``~/nwave-formal/2026-08-19-gates/report/2026-08-19-gate-
analysis.md``).
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
