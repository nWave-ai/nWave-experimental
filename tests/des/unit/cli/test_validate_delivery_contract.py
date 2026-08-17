"""Executable contract for provider-neutral DeliveryContract validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.cli import dispatch as dispatch_cli
from des.cli.__main__ import _REGISTRY
from des.cli.validate_delivery_contract import main
from tests.common.delivery_contract_fixture import seed_referenced_oracle


ROOT = Path(__file__).resolve().parents[4]
EXAMPLE = ROOT / "docs/delivery-contracts/fix-language-agnostic-contract-paths.json"


def test_valid_contract_returns_installed_schema_identity(
    tmp_path: Path, capsys
) -> None:
    contract = tmp_path / "delivery.json"
    contract.write_bytes(EXAMPLE.read_bytes())
    seed_referenced_oracle(tmp_path, json.loads(EXAMPLE.read_text(encoding="utf-8")))

    exit_code = main(
        [
            "--repo-root",
            str(tmp_path),
            "--delivery-contract",
            "delivery.json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["verdict"] == "VALID"
    assert payload["contract"] == "delivery.json"
    assert payload["digest"].startswith("sha256:")


def test_schema_invalid_contract_refuses_loudly(tmp_path: Path, capsys) -> None:
    (tmp_path / "delivery.json").write_text("{}", encoding="utf-8")

    exit_code = main(
        [
            "--repo-root",
            str(tmp_path),
            "--delivery-contract",
            "delivery.json",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "fails the thin-delivery-contract schema" in captured.err
    assert "WHAT:" in captured.err
    assert "WHY:" in captured.err
    assert "HOW:" in captured.err


def test_validator_and_dispatch_share_one_closure_digest(
    tmp_path: Path, capsys
) -> None:
    contract = tmp_path / "delivery.json"
    contract.write_bytes(EXAMPLE.read_bytes())
    seed_referenced_oracle(tmp_path, json.loads(EXAMPLE.read_text(encoding="utf-8")))
    args = ["--repo-root", str(tmp_path), "--delivery-contract", "delivery.json"]

    validate_exit = main(args)
    validate_digest = json.loads(capsys.readouterr().out)["digest"]

    dispatch_exit = dispatch_cli.main(args)
    dispatch_out = capsys.readouterr().out

    assert validate_exit == 0
    assert dispatch_exit == 0
    dispatch_digest = next(
        line.removeprefix("THIN-DELIVERY-CONTRACT-DIGEST: ")
        for line in dispatch_out.splitlines()
        if line.startswith("THIN-DELIVERY-CONTRACT-DIGEST: ")
    )
    assert validate_digest == dispatch_digest


@pytest.mark.parametrize("mutate", ["contract", "oracle"])
def test_digest_changes_when_contract_or_oracle_bytes_mutate(
    tmp_path: Path, capsys, mutate: str
) -> None:
    contract_path = tmp_path / "delivery.json"
    contract_dict = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    contract_path.write_text(json.dumps(contract_dict), encoding="utf-8")
    oracle_path = seed_referenced_oracle(tmp_path, contract_dict)
    args = ["--repo-root", str(tmp_path), "--delivery-contract", "delivery.json"]

    main(args)
    original_digest = json.loads(capsys.readouterr().out)["digest"]

    if mutate == "contract":
        contract_dict["outcome"] = contract_dict["outcome"] + " mutated."
        contract_path.write_text(json.dumps(contract_dict), encoding="utf-8")
    else:
        oracle_path.write_bytes(oracle_path.read_bytes() + b"\n# mutated\n")

    mutated_exit = main(args)
    mutated_digest = json.loads(capsys.readouterr().out)["digest"]

    assert mutated_exit == 0
    assert original_digest != mutated_digest


def test_validator_is_a_public_des_subcommand() -> None:
    row = next(row for row in _REGISTRY if row.name == "validate-delivery-contract")

    assert row.module_path == "des.cli.validate_delivery_contract"
