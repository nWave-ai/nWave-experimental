"""AST-based structural check for oracle/test files (K4 Run 10).

Run 10: ATD spliced a new test method into the MIDDLE of an existing one --
`def test_it_saves_maintenance_windows(self) -> None:` landed nested INSIDE
`test_it_works`'s own body, right before that method's own pre-existing
tail assertions (which, at the same indentation, became part of the new
nested function instead). Both are syntactically valid Python -- `ast.parse`
never raised -- but semantically broken: `test_it_saves_maintenance_windows`
is a nested function no test runner ever collects, and `test_it_works`
silently lost its own tail assertions. The crafter caught this only at
BASELINE, after implementing a full production change against it (K4 Run 9
resolved the "wrong test PATH" class of defect; this resolves "the right
path exists but the file inside it is structurally broken").

Python-only and static: no test framework is imported or executed, only the
AST is walked.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


#: A defect kind paired with the 1-based line of the offending node.
_Finding = tuple[str, int]


def _direct_test_defs(
    tree: ast.AST,
) -> list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, ast.AST]]:
    """Every `def test*`/`async def test*` function anywhere in `tree`,
    paired with its DIRECT parent node -- found by walking every node and
    inspecting only its immediate children, so the parent is exact without
    a separate parent-map."""
    pairs: list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, ast.AST]] = []
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            if isinstance(
                child, (ast.FunctionDef, ast.AsyncFunctionDef)
            ) and child.name.startswith("test"):
                pairs.append((child, parent))
    return pairs


def _has_assertion(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True when `func`'s own body contains an assertion-shaped statement:
    a bare `assert`, a `self.assert*(...)`/`assert*(...)` call, or a
    `pytest.raises(...)` call."""
    for node in ast.walk(func):
        if node is func:
            continue
        if isinstance(node, ast.Assert):
            return True
        if isinstance(node, ast.Call):
            callee = node.func
            if isinstance(callee, ast.Attribute) and callee.attr.startswith("assert"):
                return True
            if isinstance(callee, ast.Name) and callee.id.startswith("assert"):
                return True
            if isinstance(callee, ast.Attribute) and callee.attr == "raises":
                return True
    return False


def oracle_structure_findings(source: str, filename: str) -> list[_Finding]:
    """Every structural defect in one oracle/test file's source text:
    `("does-not-compile", line)` when it fails to parse; `("nested-test",
    line)` for a `test*` function whose direct parent is neither the module
    body nor a class body (defined inside another function/method); or
    `("no-assertion", line)` for a `test*` function (module- or
    class-level) with zero assertion-shaped statements in its own body.
    Empty when the file is structurally sound."""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        return [("does-not-compile", exc.lineno or 0)]

    findings: list[_Finding] = []
    for func, parent in _direct_test_defs(tree):
        if not isinstance(parent, (ast.Module, ast.ClassDef)):
            findings.append(("nested-test", func.lineno))
            continue
        if not _has_assertion(func):
            findings.append(("no-assertion", func.lineno))
    return findings


def oracle_file_findings(path: Path) -> list[_Finding]:
    """`oracle_structure_findings` read directly from `path` on disk. An
    unreadable file is not this checker's concern (existence is a separate,
    earlier check) and yields no finding here."""
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return oracle_structure_findings(source, str(path))
