"""Unit tests for the `<ATD: fill>` placeholder finder
(`des compile-contract`'s semantic-fields-left-unfilled tracking)."""

from __future__ import annotations

from des.domain.contract_placeholder_resolver import (
    PLACEHOLDER,
    find_unfilled_placeholders,
)


def _target(**overrides: object) -> dict:
    target = {
        "candidate": "pkg/mod.py",
        "overlap": "pkg/mod.py:10",
        "decision": "EXTEND",
        "justification": "a real, filled-in reason",
        "declared-imports": [],
        "contract-shape": "bounded-change",
        "boundary": {
            "failure-behavior": "real text",
            "substrate-lie": "real text",
            "substrate-probe": "real text",
            "double-blind-spot": "real text",
        },
    }
    target.update(overrides)
    return target


def test_fully_filled_contract_has_no_findings() -> None:
    contract = {"outcome": "a real outcome", "targets": {"pkg/mod.py": _target()}}
    assert find_unfilled_placeholders(contract) == []


def test_placeholder_outcome_is_found() -> None:
    contract = {"outcome": PLACEHOLDER, "targets": {"pkg/mod.py": _target()}}
    assert find_unfilled_placeholders(contract) == ["outcome"]


def test_placeholder_justification_is_found() -> None:
    contract = {
        "outcome": "real",
        "targets": {"pkg/mod.py": _target(justification=PLACEHOLDER)},
    }
    assert find_unfilled_placeholders(contract) == ["targets.pkg/mod.py.justification"]


def test_placeholder_boundary_fields_are_all_found() -> None:
    target = _target(
        boundary={
            "failure-behavior": PLACEHOLDER,
            "substrate-lie": PLACEHOLDER,
            "substrate-probe": "real",
            "double-blind-spot": "real",
        }
    )
    contract = {"outcome": "real", "targets": {"pkg/mod.py": target}}
    assert find_unfilled_placeholders(contract) == [
        "targets.pkg/mod.py.boundary.failure-behavior",
        "targets.pkg/mod.py.boundary.substrate-lie",
    ]


def test_findings_span_every_target() -> None:
    contract = {
        "outcome": "real",
        "targets": {
            "pkg/a.py": _target(justification=PLACEHOLDER),
            "pkg/b.py": _target(justification=PLACEHOLDER),
        },
    }
    assert find_unfilled_placeholders(contract) == [
        "targets.pkg/a.py.justification",
        "targets.pkg/b.py.justification",
    ]
