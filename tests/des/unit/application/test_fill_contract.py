"""Unit tests for `fill_contract_field` (`des fill-contract`'s pure core).

Ale's construction-over-file correction (2026-08-20): ATD passes VALUES to
this constructor directly -- no intermediate fill FILE, no representable
wrong shape. Mechanical fields have no `--field` choice naming them at all;
this module's own `Blocked` branches are the defense-in-depth for a caller
that somehow bypasses argparse's closed choices, never the primary gate.
"""

from __future__ import annotations

from des.application.fill_contract import (
    ALL_FIELDS,
    Blocked,
    FillContractInputs,
    Filled,
    fill_contract_field,
)
from des.domain.contract_placeholder_resolver import PLACEHOLDER


def _target(**overrides: object) -> dict:
    target = {
        "candidate": "pkg/mod.py",
        "overlap": "pkg/mod.py:10",
        "decision": "EXTEND",
        "justification": PLACEHOLDER,
        "declared-imports": [],
        "contract-shape": "bounded-change",
        "boundary": {
            "failure-behavior": PLACEHOLDER,
            "substrate-lie": PLACEHOLDER,
            "substrate-probe": PLACEHOLDER,
            "double-blind-spot": PLACEHOLDER,
        },
    }
    target.update(overrides)
    return target


def _contract(**overrides: object) -> dict:
    contract = {
        "outcome": PLACEHOLDER,
        "obligations": ["REUSE_CANDIDATE"],
        "targets": {"pkg/mod.py": _target()},
    }
    contract.update(overrides)
    return contract


def test_fills_the_top_level_outcome() -> None:
    contract = _contract()
    result = fill_contract_field(
        FillContractInputs(
            contract=contract, field="outcome", value="Widget gains a color."
        )
    )
    assert isinstance(result, Filled)
    assert result.contract["outcome"] == "Widget gains a color."
    # Every other field is untouched.
    assert result.contract["targets"]["pkg/mod.py"]["justification"] == PLACEHOLDER


def test_fills_a_target_justification() -> None:
    contract = _contract()
    result = fill_contract_field(
        FillContractInputs(
            contract=contract,
            field="justification",
            value="Widget gains a ColorValidator helper.",
            target="pkg/mod.py",
        )
    )
    assert isinstance(result, Filled)
    assert (
        result.contract["targets"]["pkg/mod.py"]["justification"]
        == "Widget gains a ColorValidator helper."
    )


def test_fills_a_boundary_subfield() -> None:
    contract = _contract()
    result = fill_contract_field(
        FillContractInputs(
            contract=contract,
            field="boundary.failure-behavior",
            value="An invalid color value is rejected.",
            target="pkg/mod.py",
        )
    )
    assert isinstance(result, Filled)
    boundary = result.contract["targets"]["pkg/mod.py"]["boundary"]
    assert boundary["failure-behavior"] == "An invalid color value is rejected."
    # Sibling boundary fields untouched.
    assert boundary["substrate-lie"] == PLACEHOLDER


def test_original_contract_is_never_mutated() -> None:
    contract = _contract()
    fill_contract_field(
        FillContractInputs(contract=contract, field="outcome", value="Real.")
    )
    assert contract["outcome"] == PLACEHOLDER


def test_refuses_target_given_for_contract_level_field() -> None:
    result = fill_contract_field(
        FillContractInputs(
            contract=_contract(),
            field="outcome",
            value="Real.",
            target="pkg/mod.py",
        )
    )
    assert isinstance(result, Blocked)
    assert "own top level" in result.why


def test_refuses_missing_target_for_target_level_field() -> None:
    result = fill_contract_field(
        FillContractInputs(contract=_contract(), field="justification", value="Real.")
    )
    assert isinstance(result, Blocked)
    assert "--target is required" in result.what


def test_refuses_an_undeclared_target() -> None:
    result = fill_contract_field(
        FillContractInputs(
            contract=_contract(),
            field="justification",
            value="Real.",
            target="pkg/nonexistent.py",
        )
    )
    assert isinstance(result, Blocked)
    assert "pkg/nonexistent.py" in result.what


def test_refuses_an_unaddressable_field() -> None:
    """Defense-in-depth: argparse's own closed `choices=` already makes
    this unreachable in the real CLI, but the pure core stays total."""
    result = fill_contract_field(
        FillContractInputs(
            contract=_contract(),
            field="declared-imports",
            value="cronsim.CronSim",
            target="pkg/mod.py",
        )
    )
    assert isinstance(result, Blocked)
    assert "declared-imports" in result.what


def test_refuses_an_empty_value() -> None:
    result = fill_contract_field(
        FillContractInputs(contract=_contract(), field="outcome", value="   \n")
    )
    assert isinstance(result, Blocked)
    assert "empty" in result.what


def test_refuses_the_literal_placeholder_as_a_value() -> None:
    result = fill_contract_field(
        FillContractInputs(contract=_contract(), field="outcome", value=PLACEHOLDER)
    )
    assert isinstance(result, Blocked)
    assert "placeholder" in result.what


def test_overwrites_an_already_filled_field_for_revision() -> None:
    """REVISE-CONTRACT: ATD re-fills an already-real field to fix a cited
    defect -- never a one-shot ratchet."""
    contract = _contract()
    first = fill_contract_field(
        FillContractInputs(contract=contract, field="outcome", value="First.")
    )
    assert isinstance(first, Filled)
    second = fill_contract_field(
        FillContractInputs(contract=first.contract, field="outcome", value="Revised.")
    )
    assert isinstance(second, Filled)
    assert second.contract["outcome"] == "Revised."


def test_all_fields_covers_every_placeholder_resolver_leaf() -> None:
    """The closed vocabulary this constructor exposes matches exactly the
    fields `contract_placeholder_resolver` tracks -- never a drifted
    superset or subset."""
    assert {
        "outcome",
        "justification",
        "boundary.failure-behavior",
        "boundary.substrate-lie",
        "boundary.substrate-probe",
        "boundary.double-blind-spot",
    } == ALL_FIELDS
