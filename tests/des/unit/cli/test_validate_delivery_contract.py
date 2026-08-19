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


def _seed_source_file(root: Path, repo_relative_path: str) -> None:
    src = ROOT / repo_relative_path
    dst = root / repo_relative_path
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src.read_bytes())


def test_declared_import_naming_a_real_symbol_is_accepted(
    tmp_path: Path, capsys
) -> None:
    """K4 matrix row 12 admission: a real base-tree symbol still validates."""
    contract_dict = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    target_path = next(iter(contract_dict["targets"]))
    contract_dict["targets"][target_path]["declared-imports"] = [
        "des.domain.repo_path_resolver.resolve_repo_root"
    ]
    contract_path = tmp_path / "delivery.json"
    contract_path.write_text(json.dumps(contract_dict), encoding="utf-8")
    seed_referenced_oracle(tmp_path, contract_dict)
    _seed_source_file(tmp_path, "src/des/domain/repo_path_resolver.py")

    exit_code = main(
        ["--repo-root", str(tmp_path), "--delivery-contract", "delivery.json"]
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["verdict"] == "VALID"


def test_declared_import_naming_a_bare_name_bound_in_the_target_file_is_accepted(
    tmp_path: Path, capsys
) -> None:
    """Run 6 false-reject repro: `repo_path_resolver.py` imports `Path` via
    `from pathlib import Path` -- a bare name bound at the top of the exact
    target file, never resolvable as a dotted module path (no file is
    literally named `Path.py`, and `pathlib` is never vendored into this
    tree). The validator must accept it, matching the K4 evidence's
    `CronSim`/`OnCalendar`/`ZoneInfo` bound-in-`hc/api/models.py` case."""
    contract_dict = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    target_path = next(iter(contract_dict["targets"]))
    del contract_dict["targets"][target_path]
    contract_dict["targets"]["src/des/domain/repo_path_resolver.py"] = {
        "candidate": "src/des/domain/repo_path_resolver.py",
        "overlap": "reuse",
        "decision": "EXTEND",
        "justification": "reuse",
        "declared-imports": ["Path", "os", "resolve_repo_root"],
        "contract-shape": "bounded-change",
        "boundary": {
            "failure-behavior": "n/a",
            "substrate-lie": "n/a",
            "substrate-probe": "n/a",
            "double-blind-spot": "n/a",
        },
    }
    contract_path = tmp_path / "delivery.json"
    contract_path.write_text(json.dumps(contract_dict), encoding="utf-8")
    seed_referenced_oracle(tmp_path, contract_dict)
    _seed_source_file(tmp_path, "src/des/domain/repo_path_resolver.py")

    exit_code = main(
        ["--repo-root", str(tmp_path), "--delivery-contract", "delivery.json"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    assert json.loads(captured.out)["verdict"] == "VALID"


def test_declared_import_naming_a_nonexistent_symbol_is_rejected(
    tmp_path: Path, capsys
) -> None:
    """K4 matrix row 12 admission: an invented symbol is rejected loudly."""
    contract_dict = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    target_path = next(iter(contract_dict["targets"]))
    contract_dict["targets"][target_path]["declared-imports"] = [
        "des.domain.this_symbol_does_not_exist_zzz"
    ]
    contract_path = tmp_path / "delivery.json"
    contract_path.write_text(json.dumps(contract_dict), encoding="utf-8")
    seed_referenced_oracle(tmp_path, contract_dict)

    exit_code = main(
        ["--repo-root", str(tmp_path), "--delivery-contract", "delivery.json"]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "des.domain.this_symbol_does_not_exist_zzz" in captured.err
    assert "WHAT:" in captured.err
    assert "WHY:" in captured.err
    assert "HOW:" in captured.err


def test_module_absent_entirely_names_the_base_revision_in_how(
    tmp_path: Path, capsys
) -> None:
    """Run 4 defect A: a declared-import whose MODULE does not exist
    anywhere in the base tree (e.g. an un-vendored third-party package) --
    the refusal must name the exact base-revision it checked against."""
    contract_dict = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    target_path = next(iter(contract_dict["targets"]))
    contract_dict["targets"][target_path]["declared-imports"] = ["cronsim.CronSim"]
    contract_path = tmp_path / "delivery.json"
    contract_path.write_text(json.dumps(contract_dict), encoding="utf-8")
    seed_referenced_oracle(tmp_path, contract_dict)

    exit_code = main(
        ["--repo-root", str(tmp_path), "--delivery-contract", "delivery.json"]
    )

    captured = capsys.readouterr()
    base_revision = contract_dict["repository"]["base-revision"]
    assert exit_code == 2
    assert "cronsim.CronSim" in captured.err
    assert f"not present at base revision {base_revision}" in captured.err
    assert "bare name bound" in captured.err.lower()
    assert "dotted base-tree module/symbol path" in captured.err.lower()
    assert "creating target" in captured.err.lower()
    assert "WHAT:" in captured.err
    assert "WHY:" in captured.err
    assert "HOW:" in captured.err


def test_self_created_symbol_cited_as_declared_import_names_the_owning_target(
    tmp_path: Path, capsys
) -> None:
    """Run 4 defect B: a declared-import citing a symbol that the SAME
    contract's own target creates -- the refusal must say so explicitly and
    name the owning target's path so the field is not left ambiguous."""
    contract_dict = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    original_target_path = next(iter(contract_dict["targets"]))
    original_target = contract_dict["targets"].pop(original_target_path)
    creating_target_path = "src/des/domain/repo_path_resolver.py"
    contract_dict["targets"][creating_target_path] = {
        **original_target,
        "candidate": creating_target_path,
        "declared-imports": [
            "des.domain.repo_path_resolver.BRAND_NEW_CONSTANT_NOT_YET_ADDED"
        ],
    }
    contract_path = tmp_path / "delivery.json"
    contract_path.write_text(json.dumps(contract_dict), encoding="utf-8")
    seed_referenced_oracle(tmp_path, contract_dict)
    _seed_source_file(tmp_path, creating_target_path)

    exit_code = main(
        ["--repo-root", str(tmp_path), "--delivery-contract", "delivery.json"]
    )

    captured = capsys.readouterr()
    base_revision = contract_dict["repository"]["base-revision"]
    assert exit_code == 2
    assert "BRAND_NEW_CONSTANT_NOT_YET_ADDED" in captured.err
    assert f"not present at base revision {base_revision}" in captured.err
    assert creating_target_path in captured.err
    assert "creates it" in captured.err
    assert "justification" in captured.err
    assert "WHAT:" in captured.err
    assert "WHY:" in captured.err
    assert "HOW:" in captured.err


def test_verification_command_naming_a_wrong_dotted_test_path_is_rejected(
    tmp_path: Path, capsys
) -> None:
    """K4 Run 9 repro: a `manage.py test`-shaped command citing a dotted
    path missing its real package prefix (mirrors the actual `api.tests.*`
    vs `hc.api.tests.*` defect) must be caught before dispatch, not
    discovered by a crafter burning 500+s finding the command is wrong."""
    contract_dict = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    contract_dict["verification-scope"]["commands"].append(
        {
            "executable": {"kind": "repository", "path": "manage.py"},
            "arguments": ["test", "build.test_thin_delivery_contract_schema"],
        }
    )
    contract_path = tmp_path / "delivery.json"
    contract_path.write_text(json.dumps(contract_dict), encoding="utf-8")
    seed_referenced_oracle(tmp_path, contract_dict)

    exit_code = main(
        ["--repo-root", str(tmp_path), "--delivery-contract", "delivery.json"]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "build.test_thin_delivery_contract_schema" in captured.err
    assert "does not resolve to a base-tree test module or file" in captured.err
    assert "WHAT:" in captured.err
    assert "WHY:" in captured.err
    assert "HOW:" in captured.err


def test_verification_command_naming_a_correct_dotted_test_path_is_accepted(
    tmp_path: Path, capsys
) -> None:
    contract_dict = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    contract_dict["verification-scope"]["commands"].append(
        {
            "executable": {"kind": "repository", "path": "manage.py"},
            "arguments": ["test", "tests.build.test_thin_delivery_contract_schema"],
        }
    )
    contract_path = tmp_path / "delivery.json"
    contract_path.write_text(json.dumps(contract_dict), encoding="utf-8")
    seed_referenced_oracle(tmp_path, contract_dict)
    _seed_source_file(tmp_path, "tests/build/test_thin_delivery_contract_schema.py")

    exit_code = main(
        ["--repo-root", str(tmp_path), "--delivery-contract", "delivery.json"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    assert json.loads(captured.out)["verdict"] == "VALID"
