"""des check-contract-shape -- mechanical Contract-Shape (Principle 11) check.

Charter: docs/product/expectations/check-contract-shape-declarations/
         des-check-contract-shape-flags-violations.md
Feature-delta: docs/feature/check-contract-shape-declarations/feature-delta.md

Runs the three mechanical Contract-Shape checks over an explicit,
caller-provided ``--files <path> [<path> ...]`` list (git-free), parsing
test functions + their docstrings via stdlib ``ast``:

  (a) every ``def test_*`` docstring contains the substring
      ``CONTRACT_SHAPE:``;
  (b) every acceptance test (a ``def test_*`` in a file whose path contains
      ``/acceptance/``) docstring contains
      ``Outcome anchor: DISCUSS Elevator Pitch``;
  (c) no test-function NAME matches the banned regex
      ``^test_.*(returns_\\d+|exit_code|calls_.*_once|status_code|http_\\d+)``.

Emits a self-explaining JSON verdict on stdout (one ``json.loads`` covers
the whole captured output). Exit 0 (clean) / 1 (>=1 violation) / 2
(malformed input: a missing, unreadable, or unparseable file -- degrade-LOUD
diagnostic naming the file, never a traceback).

Stdlib-only (GDP-7 agnostic, DES-bundle contract F-D-09): no third-party
parser, no ``import yaml``. ``ast`` is used only to locate test-function
defs + their docstrings within a single Python source file -- it does not
execute or import the scanned file.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass


_BANNED_NAME_RE = re.compile(
    r"^test_.*(returns_\d+|exit_code|calls_.*_once|status_code|http_\d+)"
)
_OUTCOME_ANCHOR = "Outcome anchor: DISCUSS Elevator Pitch"
_CONTRACT_SHAPE_TAG = "CONTRACT_SHAPE:"


class ContractShapeInputError(Exception):
    """A ``--files`` path is missing, unreadable, or fails to parse as Python."""


@dataclass(frozen=True)
class Violation:
    """One Contract-Shape violation: which test, which check, how to fix it."""

    target: str
    check: str
    how: str

    def as_dict(self) -> dict[str, str]:
        return {"target": self.target, "check": self.check, "how": self.how}


def _read_source(file_path: str) -> str:
    try:
        with open(file_path, encoding="utf-8") as handle:
            return handle.read()
    except OSError as exc:
        raise ContractShapeInputError(f"cannot read file {file_path}: {exc}") from exc


def _parse_module(file_path: str, source: str) -> ast.Module:
    try:
        return ast.parse(source, filename=file_path)
    except SyntaxError as exc:
        raise ContractShapeInputError(
            f"cannot parse file {file_path} as Python: {exc}"
        ) from exc


def _test_functions(module: ast.Module) -> list[ast.FunctionDef]:
    return [
        node
        for node in ast.walk(module)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]


def _check_a(file_path: str, func: ast.FunctionDef) -> Violation | None:
    docstring = ast.get_docstring(func) or ""
    if _CONTRACT_SHAPE_TAG in docstring:
        return None
    return Violation(
        target=f"{file_path}::{func.name}",
        check="a",
        how="add a `CONTRACT_SHAPE: <value>` line to the test docstring",
    )


def _check_b(file_path: str, func: ast.FunctionDef) -> Violation | None:
    if "/acceptance/" not in file_path.replace("\\", "/"):
        return None
    docstring = ast.get_docstring(func) or ""
    if _OUTCOME_ANCHOR in docstring:
        return None
    return Violation(
        target=f"{file_path}::{func.name}",
        check="b",
        how="add `Outcome anchor: DISCUSS Elevator Pitch` to the "
        "acceptance-test docstring",
    )


def _check_c(file_path: str, func: ast.FunctionDef) -> Violation | None:
    if not _BANNED_NAME_RE.match(func.name):
        return None
    return Violation(
        target=f"{file_path}::{func.name}",
        check="c",
        how=f"rename {func.name} to an outcome-named test (banned pattern: "
        "returns_N/exit_code/calls_*_once/status_code/http_N)",
    )


def scan_files(file_paths: list[str]) -> list[Violation]:
    """Pure scan: parse each file's test functions and run the 3 checks.

    Raises `ContractShapeInputError` naming the offending path when a file
    is missing, unreadable, or fails to parse -- callers degrade this LOUD.
    """
    violations: list[Violation] = []
    for file_path in file_paths:
        source = _read_source(file_path)
        module = _parse_module(file_path, source)
        for func in _test_functions(module):
            for check in (_check_a, _check_b, _check_c):
                violation = check(file_path, func)
                if violation is not None:
                    violations.append(violation)
    return violations


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des check-contract-shape",
        description=(
            "Run the 3 mechanical Contract-Shape (Principle 11) checks over "
            "an explicit --files list."
        ),
    )
    parser.add_argument(
        "--files",
        nargs="+",
        required=True,
        help="Explicit list of test file paths to scan (git-free).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        violations = scan_files(args.files)
    except ContractShapeInputError as exc:
        verdict = {
            "verdict": "malformed_input",
            "violation_count": 0,
            "violations": [],
            "diagnostic": str(exc),
        }
        print(json.dumps(verdict))
        return 2

    if not violations:
        verdict = {
            "verdict": "clean",
            "violation_count": 0,
            "violations": [],
            "diagnostic": "",
        }
        print(json.dumps(verdict))
        return 0

    verdict = {
        "verdict": "violations_found",
        "violation_count": len(violations),
        "violations": [v.as_dict() for v in violations],
        "diagnostic": "",
    }
    print(json.dumps(verdict))
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
