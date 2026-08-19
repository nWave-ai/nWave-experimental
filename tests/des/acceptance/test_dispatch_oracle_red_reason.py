"""Acceptance coverage for the BASE oracle-execution probe at `des dispatch`
(K4 Run 13). Never switchable off (GDP-7) -- fires on every dispatch call,
including this repo's own pytest run, through a real, isolated `tmp_path`
subprocess each time (no recursion risk). Language-agnostic (roadmap:
"language agnostic is an outcome constraint, not authorization to build
or retain a universal language-adapter framework"): "already green for
RED_TO_GREEN", "right-reason RED" (a declared symbol named) and
"UNACCEPTABLE_BUILD" (a language-neutral build/compile marker, output
quoted) are the three distinguished, still-language-agnostic outcomes;
everything else degrades to an informational note, never a refusal.
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.common.delivery_contract_fixture import (
    load_valid_contract,
)
from tests.common.in_process_cli import run_cli_in_process


def _run(*args: str, cwd: Path) -> tuple[int, str, str]:
    return run_cli_in_process(["dispatch", *args], cwd=cwd)


def _seed_contract_with_synthetic_oracle(
    root: Path, oracle_source: str, *, route: str = "RED_TO_GREEN"
) -> Path:
    """A minimal, schema-shaped contract whose oracle is a real file this
    probe actually executes -- distinct from the shared checked-in fixture
    (`tests/common/delivery_contract_fixture.py`), which carries its own
    dedicated genuinely-RED oracle body for this same reason.

    CI reproduction (env -i, stripped PATH, no shell activation): a
    repo-relative SYMLINK to `sys.executable` broke Python's own venv
    self-detection when invoked as a subprocess (`No module named pytest`,
    even though the symlink's target genuinely has pytest installed) --
    reproduced locally only by accident, since a stray user-site pytest
    install happened to mask the failure on this machine. `"kind":
    "toolchain","name":"python"` sidesteps the symlink entirely: `uv run`
    already prepends `.venv/bin` to PATH for every child process, so a
    bare `python` resolves directly to the venv's own real entry point
    (verified against the exact CI-like `env -i ... uv run pytest` repro),
    with no indirection to break.

    `--import-mode=importlib` is likewise explicit, not incidental: this
    isolated `tmp_path` has no `pyproject.toml` of its own, so an
    unqualified inner pytest silently falls back to its "prepend" default
    -- which inserts only `tmp_path/tests` (not `tmp_path`) onto
    `sys.path`, so `tests.broken_helper`-style dotted imports resolve to
    NOTHING (`ModuleNotFoundError`), masking the real `SyntaxError` this
    probe exists to surface. This repo's own `pyproject.toml` already
    pins `--import-mode=importlib` for every other pytest invocation;
    matching it here is fixing an inconsistency, not adding one."""
    contract = load_valid_contract()
    contract["delivery-route"] = route
    contract["acceptance-tests"]["locator"] = "tests/synthetic_oracle.py"
    contract["verification-scope"]["commands"] = [
        {
            "executable": {"kind": "toolchain", "name": "python"},
            "arguments": [
                "-m",
                "pytest",
                "-q",
                "--import-mode=importlib",
                "tests/synthetic_oracle.py",
            ],
        }
    ]
    for target_path, target in contract["targets"].items():
        target["justification"] = (
            "The new NotBuiltYet symbol lives beside it "
            f"({target_path}:1, insertion point)."
        )
    oracle_path = root / "tests/synthetic_oracle.py"
    oracle_path.parent.mkdir(parents=True, exist_ok=True)
    oracle_path.write_text(oracle_source, encoding="utf-8")
    path = root / "delivery-contract.json"
    path.write_text(json.dumps(contract), encoding="utf-8")
    return path


def _seed_broken_helper(root: Path) -> None:
    """A syntax error in a file the oracle IMPORTS -- real execution (this
    probe) is the only thing that can see it at all now that there is no
    static structure checker."""
    helper = root / "tests" / "broken_helper.py"
    helper.parent.mkdir(parents=True, exist_ok=True)
    helper.write_text("def broken(:\n    pass\n", encoding="utf-8")


def test_syntax_error_in_an_imported_helper_is_refused_with_quoted_output(
    tmp_path: Path,
) -> None:
    """A SyntaxError matches the language-neutral build-marker table --
    refused, quoting the real output, before any crafter mutation."""
    _seed_broken_helper(tmp_path)
    contract_path = _seed_contract_with_synthetic_oracle(
        tmp_path,
        "from tests.broken_helper import broken\n\n"
        "def test_it():\n    assert broken() == 1\n",
    )

    exit_code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        contract_path.name,
        cwd=tmp_path,
    )

    assert exit_code != 0
    assert "quoted output" in err
    assert "WHAT:" in err
    assert "WHY:" in err
    assert "HOW:" in err


def test_oracle_with_no_symbol_and_no_build_marker_is_informational(
    tmp_path: Path,
) -> None:
    """A fixture/setup gap this classifier has no vocabulary for --
    informational only, dispatch still succeeds."""
    contract_path = _seed_contract_with_synthetic_oracle(
        tmp_path,
        "def test_it():\n    raise RuntimeError('unrelated dependency missing')\n",
    )

    exit_code, out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        contract_path.name,
        cwd=tmp_path,
    )

    assert exit_code == 0, err
    assert "INFO:" in err
    assert "INDETERMINATE" in err
    assert out.startswith("THIN-DELIVERY-CONTRACT: ")


def test_already_green_oracle_for_red_to_green_is_refused(tmp_path: Path) -> None:
    contract_path = _seed_contract_with_synthetic_oracle(
        tmp_path, "def test_it():\n    assert 1 == 1\n"
    )

    exit_code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        contract_path.name,
        cwd=tmp_path,
    )

    assert exit_code != 0
    assert "already passes at BASE" in err


def test_oracle_failing_for_the_right_reason_is_accepted(tmp_path: Path) -> None:
    contract_path = _seed_contract_with_synthetic_oracle(
        tmp_path,
        "from pkg.mod import NotBuiltYet\n\n"
        "def test_it():\n    assert NotBuiltYet() == 1\n",
    )

    exit_code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        contract_path.name,
        cwd=tmp_path,
    )

    assert exit_code == 0, err
