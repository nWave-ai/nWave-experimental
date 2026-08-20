"""CLI acceptance tests for `des fill-contract`
(Ale's construction-over-file correction, 2026-08-20)."""

from __future__ import annotations

import json
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process


def _run(*args: str, cwd: Path, stdin: str | None = None) -> tuple[int, str, str]:
    return run_cli_in_process(["fill-contract", *args], cwd=cwd, stdin_text=stdin)


_CONTRACT = {
    "schema-version": "1.2",
    "delivery-id": "widget-color",
    "repository": {"worktree": ".", "base-revision": "git-sha1:" + "a" * 40},
    "outcome": "<ATD: fill>",
    "targets": {
        "pkg/widget.py": {
            "candidate": "pkg/widget.py",
            "overlap": "pkg/widget.py:5",
            "decision": "EXTEND",
            "justification": "<ATD: fill>",
            "declared-imports": [],
            "contract-shape": "bounded-change",
            "boundary": {
                "failure-behavior": "<ATD: fill>",
                "substrate-lie": "<ATD: fill>",
                "substrate-probe": "<ATD: fill>",
                "double-blind-spot": "<ATD: fill>",
            },
        }
    },
    "paradigm": "object_oriented",
    "delivery-route": "RED_TO_GREEN",
    "obligations": ["REUSE_CANDIDATE"],
    "acceptance-tests": {"locator": "pkg/tests/test_widget_color.py"},
    "verification-scope": {
        "commands": [
            {
                "executable": {"kind": "toolchain", "name": "python"},
                "arguments": ["-m", "pytest", "-q", "pkg/tests/test_widget_color.py"],
            }
        ]
    },
    "applicability": {"independent-review": False, "examine": True},
    "budget": {"token-limit": 2_000_000, "wall-clock-minutes": 30},
}


def _seed(repo_root: Path, contract: dict | None = None) -> Path:
    contracts_dir = repo_root / "docs" / "delivery-contracts"
    contracts_dir.mkdir(parents=True, exist_ok=True)
    path = contracts_dir / "widget-color.json"
    path.write_text(json.dumps(contract if contract is not None else _CONTRACT))
    return path


def test_fills_a_target_level_field_and_writes_it_back(tmp_path: Path) -> None:
    contract_path = _seed(tmp_path)
    code, out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--target",
        "pkg/widget.py",
        "--field",
        "justification",
        cwd=tmp_path,
        stdin="Widget gains a ColorValidator helper.\n",
    )
    assert code == 0, err
    assert "DELIVERY-CONTRACT-FILLED: justification (pkg/widget.py)" in out
    assert "CONTRACT-FILL-STATUS: INCOMPLETE" in out

    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    assert (
        contract["targets"]["pkg/widget.py"]["justification"]
        == "Widget gains a ColorValidator helper."
    )


def test_fills_the_contract_level_outcome(tmp_path: Path) -> None:
    _seed(tmp_path)
    code, out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--field",
        "outcome",
        cwd=tmp_path,
        stdin="Widget gains a validated color attribute.\n",
    )
    assert code == 0, err
    assert "DELIVERY-CONTRACT-FILLED: outcome" in out
    assert "(pkg/widget.py)" not in out.splitlines()[0]


def test_status_reports_every_remaining_field_without_writing(tmp_path: Path) -> None:
    contract_path = _seed(tmp_path)
    before = contract_path.read_bytes()

    code, out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--status",
        cwd=tmp_path,
    )
    assert code == 0, err
    assert "CONTRACT-FILL-STATUS: INCOMPLETE" in out
    assert "UNFILLED: outcome" in out
    assert "UNFILLED: targets.pkg/widget.py.justification" in out
    assert contract_path.read_bytes() == before


def test_status_reports_complete_once_every_field_is_filled(tmp_path: Path) -> None:
    contract = json.loads(json.dumps(_CONTRACT))
    contract["outcome"] = "Real outcome."
    target = contract["targets"]["pkg/widget.py"]
    target["justification"] = "Real justification."
    target["boundary"] = {
        "failure-behavior": "Real.",
        "substrate-lie": "Real.",
        "substrate-probe": "Real.",
        "double-blind-spot": "Real.",
    }
    _seed(tmp_path, contract)

    code, out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--status",
        cwd=tmp_path,
    )
    assert code == 0, err
    assert out.strip() == "CONTRACT-FILL-STATUS: COMPLETE"


def test_refuses_a_mechanical_field_name_at_argv_parsing(tmp_path: Path) -> None:
    _seed(tmp_path)
    code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--target",
        "pkg/widget.py",
        "--field",
        "declared-imports",
        cwd=tmp_path,
        stdin="cronsim.CronSim\n",
    )
    assert code != 0
    assert "WHAT:" in err and "WHY:" in err and "HOW:" in err
    assert "invalid choice" in err.lower() or "declared-imports" in err


def test_refuses_an_undeclared_target(tmp_path: Path) -> None:
    _seed(tmp_path)
    code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--target",
        "pkg/nonexistent.py",
        "--field",
        "justification",
        cwd=tmp_path,
        stdin="Real value.\n",
    )
    assert code != 0
    assert "pkg/nonexistent.py" in err
    assert "WHAT:" in err and "WHY:" in err and "HOW:" in err


def test_refuses_when_no_contract_exists_yet(tmp_path: Path) -> None:
    code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--field",
        "outcome",
        cwd=tmp_path,
        stdin="Real value.\n",
    )
    assert code != 0
    assert "no contract exists" in err
    assert "des compile-contract" in err


def test_revision_overwrites_an_already_filled_field(tmp_path: Path) -> None:
    contract_path = _seed(tmp_path)
    _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--field",
        "outcome",
        cwd=tmp_path,
        stdin="First outcome.\n",
    )
    code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--field",
        "outcome",
        cwd=tmp_path,
        stdin="Revised outcome.\n",
    )
    assert code == 0, err
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    assert contract["outcome"] == "Revised outcome."


def test_refuses_relative_repo_root(tmp_path: Path) -> None:
    _seed(tmp_path)
    code, _out, err = _run(
        "--repo-root",
        ".",
        "--delivery-id",
        "widget-color",
        "--status",
        cwd=tmp_path,
    )
    assert code != 0
    assert "absolute" in err


def test_field_and_status_are_mutually_exclusive(tmp_path: Path) -> None:
    _seed(tmp_path)
    code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--field",
        "outcome",
        "--status",
        cwd=tmp_path,
        stdin="Real value.\n",
    )
    assert code != 0
    assert "WHAT:" in err
