"""Acceptance coverage for the oracle language boundary (K4 sister defect,
SF run, verified chain; then Ale's roadmap directive, 2026-08-19: "language
agnostic is an outcome constraint, not authorization to build or retain a
universal language-adapter framework").

A valid Go oracle whose first line is `// ADR-016` must never be refused as
`does-not-compile` -- Python's `ast.parse` reads `016` as a leading-zero
decimal integer literal, a genuine SyntaxError on perfectly valid Go. The
fix that shipped is not a per-language adapter (built once, then deleted --
"removal before refactoring"): there is no more `does-not-compile` claim
for ANY language, Python included. `des dispatch` runs ONE check: a
declared-symbol token match is RED (accepted); a language-neutral, small,
extensible build/compile-marker match is `UNACCEPTABLE_BUILD` (refused,
the real tool's own output quoted -- never a language-specific diagnosis
like "syntax error at line 1"); everything else is informational; "already
green for RED_TO_GREEN" is the one other refusal, scoped to Python-shaped
oracle-linked commands (extending that to a non-Python command has no
reliable linkage signal yet -- a documented, tested scope limit, not a
silent gap).

Real `go` is not assumed present -- each test seeds a tiny, repo-relative
FAKE `go` executable (a shell script) as the contract's own declared
command, so the real bounded-subprocess execution path is genuinely
exercised without an external toolchain dependency.
"""

from __future__ import annotations

import json
import stat
from pathlib import Path

from tests.common.delivery_contract_fixture import load_valid_contract
from tests.common.in_process_cli import run_cli_in_process


def _run(*args: str, cwd: Path) -> tuple[int, str, str]:
    return run_cli_in_process(["dispatch", *args], cwd=cwd)


def _seed_fake_go(root: Path, script: str) -> None:
    fake_go = root / "go"
    fake_go.write_text(f"#!/bin/sh\n{script}\n", encoding="utf-8")
    fake_go.chmod(fake_go.stat().st_mode | stat.S_IEXEC)


def _seed_contract_with_oracle(
    root: Path,
    oracle_relative: str,
    oracle_source: str,
    command: dict,
    *,
    route: str = "RED_TO_GREEN",
) -> Path:
    contract = load_valid_contract()
    contract["delivery-route"] = route
    contract["acceptance-tests"]["locator"] = oracle_relative
    contract["verification-scope"]["commands"] = [command]
    for target_path, target in contract["targets"].items():
        target["justification"] = (
            "The new NotBuiltYet symbol lives beside it "
            f"({target_path}:1, insertion point)."
        )
    oracle_path = root / oracle_relative
    oracle_path.parent.mkdir(parents=True, exist_ok=True)
    oracle_path.write_text(oracle_source, encoding="utf-8")
    path = root / "delivery-contract.json"
    path.write_text(json.dumps(contract), encoding="utf-8")
    return path


_GO_ORACLE_SOURCE = "// ADR-016\nfunc TestFoo(t *testing.T) {}\n"


def _go_command() -> dict:
    return {
        "executable": {"kind": "repository", "path": "go"},
        "arguments": ["test", "./..."],
    }


def test_valid_go_oracle_is_never_refused_as_does_not_compile(tmp_path: Path) -> None:
    """K4 sister repro exactly: `// ADR-016` first line must never trigger
    a Python does-not-compile refusal -- there is no more such refusal for
    any language, Python included (the structure checker that produced it
    is deleted)."""
    _seed_fake_go(
        tmp_path,
        'echo "--- FAIL: TestFoo" >&2\necho "undefined: NotBuiltYet" >&2\nexit 1',
    )
    contract_path = _seed_contract_with_oracle(
        tmp_path, "foo_test.go", _GO_ORACLE_SOURCE, _go_command()
    )

    exit_code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        contract_path.name,
        cwd=tmp_path,
    )

    assert "does-not-compile" not in err
    assert exit_code == 0, err


def test_go_oracle_failing_for_the_right_reason_is_valid(tmp_path: Path) -> None:
    """Right-reason RED -> VALID, any language, a plain declared-symbol
    token match."""
    _seed_fake_go(
        tmp_path,
        'echo "--- FAIL: TestFoo" >&2\necho "undefined: NotBuiltYet" >&2\nexit 1',
    )
    contract_path = _seed_contract_with_oracle(
        tmp_path, "foo_test.go", _GO_ORACLE_SOURCE, _go_command()
    )

    exit_code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        contract_path.name,
        cwd=tmp_path,
    )

    assert exit_code == 0, err


def test_go_oracle_build_broken_without_declared_symbol_is_refused_with_quoted_output(
    tmp_path: Path,
) -> None:
    """UNACCEPTABLE_BUILD: a build/compile marker (go's own output) is
    refused, the REAL output quoted -- never a fabricated Python-specific
    "syntax error at line 1" diagnosis against non-Python output."""
    _seed_fake_go(
        tmp_path,
        'echo "# command-line-arguments" >&2\n'
        'echo "./foo_test.go:1:1: syntax error: unexpected newline" >&2\n'
        "exit 2",
    )
    contract_path = _seed_contract_with_oracle(
        tmp_path, "foo_test.go", _GO_ORACLE_SOURCE, _go_command()
    )

    exit_code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        contract_path.name,
        cwd=tmp_path,
    )

    assert exit_code != 0
    assert "syntax error at line 1" not in err.lower()
    assert "unexpected newline" in err
    assert "quoted output" in err
    assert "WHAT:" in err and "WHY:" in err and "HOW:" in err


def test_go_oracle_broken_with_no_symbol_and_no_build_marker_is_informational(
    tmp_path: Path,
) -> None:
    """Neither a declared symbol nor a build marker -- informational only,
    never a refusal, never a fabricated diagnosis."""
    _seed_fake_go(tmp_path, 'echo "panic: unrelated dependency missing" >&2\nexit 1')
    contract_path = _seed_contract_with_oracle(
        tmp_path, "foo_test.go", _GO_ORACLE_SOURCE, _go_command()
    )

    exit_code, out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        contract_path.name,
        cwd=tmp_path,
    )

    assert exit_code == 0, err
    assert "does-not-compile" not in err
    assert "INFO:" in err
    assert "INDETERMINATE" in err
    assert out.startswith("THIN-DELIVERY-CONTRACT: ")


def test_go_already_green_for_red_to_green_is_not_flagged_documented_scope_limit(
    tmp_path: Path,
) -> None:
    """Documented, tested scope limit: ALREADY_GREEN detection stays scoped
    to Python-shaped oracle-linked commands -- there is no reliable non-
    Python file/package-to-oracle-locator linkage signal yet. Extending it
    naively (assume every non-Python command is linked) risks reintroducing
    the false-positive class CI already caught once for this repo's own
    shared fixture (`git diff --check` legitimately passing under
    RED_TO_GREEN)."""
    _seed_fake_go(tmp_path, "exit 0")
    contract_path = _seed_contract_with_oracle(
        tmp_path, "foo_test.go", _GO_ORACLE_SOURCE, _go_command()
    )

    exit_code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        contract_path.name,
        cwd=tmp_path,
    )

    assert exit_code == 0, err
    assert "already passes at BASE" not in err


def test_unknown_language_oracle_never_ast_parsed_right_reason_red_is_valid(
    tmp_path: Path,
) -> None:
    """ "unknown -> still the same single check": a `.zig` oracle and a
    `zig test` command this project names nowhere in its own code must
    never crash, never claim `does-not-compile`, and accept a right-reason
    declared-symbol match exactly like Go and Python do."""
    zig = tmp_path / "zig"
    zig.write_text(
        '#!/bin/sh\necho "test.zig:3:5: error: undefined identifier NotBuiltYet" >&2\nexit 1\n',
        encoding="utf-8",
    )
    zig.chmod(zig.stat().st_mode | stat.S_IEXEC)
    contract_path = _seed_contract_with_oracle(
        tmp_path,
        "test.zig",
        "// not Python, not Go -- an unrecognized language\n"
        'test "it awaits NotBuiltYet" {}\n',
        {
            "executable": {"kind": "repository", "path": "zig"},
            "arguments": ["test", "test.zig"],
        },
    )

    exit_code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        contract_path.name,
        cwd=tmp_path,
    )

    assert "does-not-compile" not in err
    assert exit_code == 0, err


def test_python_oracle_syntax_error_is_refused_with_quoted_output(
    tmp_path: Path,
) -> None:
    """Regression: Python oracles go through the exact same single check
    now -- a SyntaxError is UNACCEPTABLE_BUILD, same as Go's build marker,
    no dedicated `does-not-compile` refusal."""
    contract_path = _seed_contract_with_oracle(
        tmp_path,
        "tests/broken_oracle.py",
        "def test_it(:\n    pass\n",
        {
            "executable": {"kind": "toolchain", "name": "python"},
            "arguments": ["-m", "pytest", "-q", "tests/broken_oracle.py"],
        },
    )

    exit_code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        contract_path.name,
        cwd=tmp_path,
    )

    assert exit_code != 0
    assert "does-not-compile" not in err
    assert "quoted output" in err
    assert "WHAT:" in err and "WHY:" in err and "HOW:" in err


def test_python_oracle_already_green_for_red_to_green_is_still_refused(
    tmp_path: Path,
) -> None:
    """Regression: the ALREADY_GREEN refusal stays intact for Python-shaped
    oracle-linked commands."""
    contract_path = _seed_contract_with_oracle(
        tmp_path,
        "tests/already_green_oracle.py",
        "def test_it():\n    assert 1 == 1\n",
        {
            "executable": {"kind": "toolchain", "name": "python"},
            "arguments": ["-m", "pytest", "-q", "tests/already_green_oracle.py"],
        },
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
