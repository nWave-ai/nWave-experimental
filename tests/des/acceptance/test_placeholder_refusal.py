"""Acceptance contract: `des dispatch` and `des validate-delivery-contract`
both refuse a contract still carrying `des compile-contract`'s literal
`<ATD: fill>` skeleton placeholder (ADR-SSOT-002 Section 4/4b item 1) --
an unfilled skeleton can never reach DELIVER by accident.
"""

from __future__ import annotations

import json
from pathlib import Path

from des.domain.contract_placeholder_resolver import PLACEHOLDER
from tests.common.delivery_contract_fixture import (
    load_valid_contract,
    seed_referenced_oracle,
)
from tests.common.in_process_cli import run_cli_in_process


_REPO_ROOT = Path(__file__).resolve().parents[3]


def _seed_contract_with_placeholder(root: Path) -> str:
    contract = load_valid_contract()
    target_path = next(iter(contract["targets"]))
    contract["targets"][target_path]["justification"] = PLACEHOLDER
    seed_referenced_oracle(root, contract)
    rel_path = "delivery-contract.json"
    (root / rel_path).write_text(json.dumps(contract), encoding="utf-8")
    return rel_path


def test_dispatch_refuses_a_placeholder_justification(tmp_path: Path) -> None:
    rel_path = _seed_contract_with_placeholder(tmp_path)
    code, _out, err = run_cli_in_process(
        ["dispatch", "--repo-root", str(tmp_path), "--delivery-contract", rel_path],
        cwd=_REPO_ROOT,
    )
    assert code != 0
    assert PLACEHOLDER in err
    assert "WHAT:" in err and "WHY:" in err and "HOW:" in err


def test_validate_delivery_contract_refuses_a_placeholder_justification(
    tmp_path: Path,
) -> None:
    rel_path = _seed_contract_with_placeholder(tmp_path)
    code, _out, err = run_cli_in_process(
        [
            "validate-delivery-contract",
            "--repo-root",
            str(tmp_path),
            "--delivery-contract",
            rel_path,
        ],
        cwd=_REPO_ROOT,
    )
    assert code != 0
    assert PLACEHOLDER in err
    assert "WHAT:" in err and "WHY:" in err and "HOW:" in err


def test_dispatch_accepts_a_fully_filled_contract(tmp_path: Path) -> None:
    contract = load_valid_contract()
    seed_referenced_oracle(tmp_path, contract)
    rel_path = "delivery-contract.json"
    (tmp_path / rel_path).write_text(json.dumps(contract), encoding="utf-8")
    code, _out, err = run_cli_in_process(
        ["dispatch", "--repo-root", str(tmp_path), "--delivery-contract", rel_path],
        cwd=_REPO_ROOT,
    )
    assert code == 0, err
