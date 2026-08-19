"""Acceptance coverage for the whole-suite-scope refusal (K4 Run 12).

Run 12 debrief: the subject's root CLAUDE.md already stated a whole-suite
test command that the contract's `verification-scope.commands` never
carried; only the new oracle's own narrow test ran at BASELINE/GREEN, and
3 reviewer rounds were needed to surface regressions outside it.
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.common.delivery_contract_fixture import (
    load_valid_contract,
    seed_referenced_oracle,
)
from tests.common.in_process_cli import run_cli_in_process


_WHOLE_SUITE_LINE = (
    "- Run the subject's own tests: "
    "`k4-fixture-venv/bin/python manage.py test hc.api --noinput`\n"
)


def _run(*args: str, cwd: Path) -> tuple[int, str, str]:
    return run_cli_in_process(["dispatch", *args], cwd=cwd)


def _seed_contract(root: Path, *, extra_command: dict | None = None) -> Path:
    contract = load_valid_contract()
    seed_referenced_oracle(root, contract)
    if extra_command is not None:
        contract["verification-scope"]["commands"].append(extra_command)
    path = root / "delivery-contract.json"
    path.write_text(json.dumps(contract), encoding="utf-8")
    return path


def test_no_claude_md_means_nothing_to_check(tmp_path: Path) -> None:
    contract_path = _seed_contract(tmp_path)

    exit_code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        contract_path.name,
        cwd=tmp_path,
    )

    assert exit_code == 0
    assert err == ""


def test_declared_whole_suite_command_missing_from_scope_is_refused(
    tmp_path: Path,
) -> None:
    (tmp_path / "CLAUDE.md").write_text(_WHOLE_SUITE_LINE, encoding="utf-8")
    contract_path = _seed_contract(tmp_path)

    exit_code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        contract_path.name,
        cwd=tmp_path,
    )

    assert exit_code != 0
    assert "WHAT:" in err
    assert "whole-suite" in err
    assert "hc.api" in err
    assert "WHY:" in err
    assert "HOW:" in err


def test_declared_whole_suite_command_present_in_scope_is_accepted(
    tmp_path: Path,
) -> None:
    (tmp_path / "CLAUDE.md").write_text(_WHOLE_SUITE_LINE, encoding="utf-8")
    contract_path = _seed_contract(
        tmp_path,
        extra_command={
            "executable": {"kind": "toolchain", "name": "python"},
            "arguments": ["manage.py", "test", "hc.api"],
        },
    )

    exit_code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        contract_path.name,
        cwd=tmp_path,
    )

    assert exit_code == 0
    assert err == ""
