"""Guard against a fifteenth copy of the single-line-JSON-stdout `_emit` shape
(D03, mikado 2026-07-28). Fourteen `des.cli` modules independently defined
the same helper -- byte for byte -- before commit c9faf98cf collapsed them
into `des.cli._emit_json.emit_json_line`. Nothing mechanical stopped a
fifteenth copy from reappearing tomorrow; this test is that mechanism.

PROPERTY, not designation. The guard flags a module for what its function's
BODY reduces to (an AST shape: exactly one statement, `print(json.dumps(x))`
where `x` is that function's sole parameter), never for what the function is
NAMED. A copy named `_out`, `_write_json`, or anything else is caught the
same as one named `_emit` -- and, symmetrically, a function named `_emit`
that does something else entirely (there are three such shapes on this same
CLI surface -- see below) is NOT flagged. See `test_the_guard_can_fail`,
which plants a differently-named fifteenth copy and watches it go red.

The canonical definition (`des/cli/_emit_json.py`) is excluded from the scan
by construction: a definition cannot duplicate itself. That is the ONE
designation-keyed exception, and it is inherent to what "duplicate" means,
not a name-based allow-list for the call sites.
"""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_DES_CLI = REPO_ROOT / "src" / "des" / "cli"
CANONICAL_MODULE = SRC_DES_CLI / "_emit_json.py"


def _is_single_line_json_stdout_shape(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    """True iff `func`'s body is EXACTLY `print(json.dumps(<sole-param>))`.

    Property-based: independent of the function's name, independent of its
    parameter's type annotation. A docstring, if present, is ignored; any
    OTHER statement, or any keyword argument on either call, takes the
    function out of the shape (that keyword is exactly how the sort_keys /
    dual-stream variants differ).
    """
    args = func.args
    if len(args.args) != 1 or args.vararg or args.kwonlyargs or args.kwarg:
        return False
    param_name = args.args[0].arg

    body = [
        stmt
        for stmt in func.body
        if not (
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
        )
    ]
    if len(body) != 1:
        return False

    (stmt,) = body
    if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
        return False
    outer = stmt.value
    if not (isinstance(outer.func, ast.Name) and outer.func.id == "print"):
        return False
    if outer.keywords or len(outer.args) != 1:
        return False

    inner = outer.args[0]
    if not isinstance(inner, ast.Call):
        return False
    if not (
        isinstance(inner.func, ast.Attribute)
        and inner.func.attr == "dumps"
        and isinstance(inner.func.value, ast.Name)
        and inner.func.value.id == "json"
    ):
        return False
    if inner.keywords or len(inner.args) != 1:
        return False

    sole_arg = inner.args[0]
    return isinstance(sole_arg, ast.Name) and sole_arg.id == param_name


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _reimplementations_in(cli_dir: Path) -> list[str]:
    offenders: list[str] = []
    for path in sorted(cli_dir.glob("*.py")):
        if path == CANONICAL_MODULE:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and _is_single_line_json_stdout_shape(
                node
            ):
                offenders.append(f"{_display_path(path)}:{node.name}")
    return offenders


def test_no_des_cli_module_reimplements_the_single_line_json_stdout_shape():
    offenders = _reimplementations_in(SRC_DES_CLI)
    assert offenders == [], (
        "the following des.cli function(s) reduce to the exact "
        "print(json.dumps(<param>)) shape already shared as "
        "des.cli._emit_json.emit_json_line -- import it instead of "
        f"reimplementing it: {offenders}"
    )


def test_the_guard_can_fail(tmp_path: Path):
    """Prove the guard fails for the right reason: plant a fifteenth copy
    under a NAME the guard has never seen (`_write_json`, not `_emit`) in an
    isolated directory, and watch it go red -- then remove it and confirm
    the same directory goes green again."""
    shadow_dir = tmp_path / "cli"
    shadow_dir.mkdir()
    planted = shadow_dir / "some_new_gate.py"
    planted.write_text(
        "import json\n\n\n"
        "def _write_json(record: dict[str, object]) -> None:\n"
        "    print(json.dumps(record))\n",
        encoding="utf-8",
    )

    red_offenders = _reimplementations_in(shadow_dir)
    assert any(o.endswith("some_new_gate.py:_write_json") for o in red_offenders), (
        "planting a differently-named fifteenth copy did not trip the guard "
        "-- it is keying on the function name, not the body shape"
    )

    planted.unlink()
    green_offenders = _reimplementations_in(shadow_dir)
    assert green_offenders == [], (
        "removing the planted copy should clear the guard, and it did not"
    )


def test_the_guard_spares_its_own_canonical_definition():
    """The real des.cli._emit_json.py contains the exact banned shape as ITS
    OWN definition -- confirm the by-construction exclusion actually fires
    on the real scan, not merely by inspection of the source."""
    offenders = _reimplementations_in(SRC_DES_CLI)
    assert not any("_emit_json.py" in o for o in offenders), (
        "the guard flagged its own canonical reference module"
    )
