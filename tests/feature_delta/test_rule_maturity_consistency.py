"""
Consistency guard for nWave/data/feature-delta-rule-maturity.json (DD-O5, CI Stage 2).

Verifies structural integrity of the rule-maturity manifest so that
patch_pyproject.py, --enforce eligibility, and CI gates all operate on
a well-formed data file.

Test Budget: 3 behaviors x 2 = 6 unit tests max (using 4).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


_MATURITY_FILE = (
    Path(__file__).parent.parent.parent
    / "nWave"
    / "data"
    / "feature-delta-rule-maturity.json"
)

_REQUIRED_RULE_FIELDS = {"status"}
_VALID_STATUSES = {"stable", "pending", "experimental"}
_REQUIRED_TOP_LEVEL = {"schema_version", "rules", "enforce_eligibility"}


@pytest.fixture(scope="module")
def maturity_data() -> dict:
    assert _MATURITY_FILE.exists(), f"Rule maturity file missing: {_MATURITY_FILE}"
    return json.loads(_MATURITY_FILE.read_text(encoding="utf-8"))


def test_maturity_file_has_required_top_level_fields(maturity_data: dict) -> None:
    missing = _REQUIRED_TOP_LEVEL - set(maturity_data.keys())
    assert not missing, f"Missing top-level fields: {missing}"


def test_every_rule_has_required_fields(maturity_data: dict) -> None:
    violations: list[str] = []
    for rule_id, rule_def in maturity_data["rules"].items():
        missing = _REQUIRED_RULE_FIELDS - set(rule_def.keys())
        if missing:
            violations.append(f"Rule {rule_id!r} missing fields: {missing}")
    assert not violations, "\n".join(violations)


def test_every_rule_has_valid_status(maturity_data: dict) -> None:
    violations: list[str] = []
    for rule_id, rule_def in maturity_data["rules"].items():
        status = rule_def.get("status")
        if status not in _VALID_STATUSES:
            violations.append(
                f"Rule {rule_id!r} has invalid status {status!r}; "
                f"expected one of {_VALID_STATUSES}"
            )
    assert not violations, "\n".join(violations)


def test_enforce_eligibility_required_rules_are_all_present(
    maturity_data: dict,
) -> None:
    eligibility = maturity_data["enforce_eligibility"]
    required = eligibility.get("required_stable", [])
    defined_rules = set(maturity_data["rules"].keys())
    missing = set(required) - defined_rules
    assert not missing, (
        f"enforce_eligibility.required_stable references undefined rules: {missing}"
    )
