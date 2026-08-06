"""Guard against a fifth hand-rolled scaffold-verdict CLI reappearing (D49,
mikado 2026-07-29). Four `des.cli` scaffold generators (charter-scaffold,
examine-fixture, flavor-scaffold) used to
independently re-derive the same "print a verdict-envelope dict as JSON, map
its `verdict` field to an exit code" shape -- collapsed into
`des.cli._scaffold_core.emit_scaffold_verdict`. Nothing mechanical stopped a
fifth copy from reappearing tomorrow; this test is that mechanism.

Mirrors `test_no_duplicate_emit_json_helper.py`'s own house style and its own
explicit instruction (D49 mandate): "decide on the PROPERTY, never the
DESIGNATION". The guard flags a function for what its BODY reduces to (an
AST shape: exactly `print(json.dumps(<param>))` followed by
`return 0 if <param>.get("verdict") == <accepted> else 1`), never for what
the function is NAMED -- see `test_the_guard_can_fail`, which plants a
differently-named fifth copy and watches it go red.

WHAT THIS DOES **NOT** FLAG. `charter_scaffold._degrade` /
`_emit_single_scaffold_result` / `_run_slice_plan`'s tail, and
each scaffold's private `_emit`, now all call
`emit_scaffold_verdict` directly (a single `return emit_scaffold_verdict(
{...})` statement) -- they do NOT re-derive the print+ternary shape, so the
guard does not (and should not) flag them; see
`test_the_guard_spares_the_migrated_scaffold_callers`. The ~20 unrelated
`return 0 if X else 1` exit-code idioms elsewhere on `des.cli` (one of the
most common conventions on this CLI surface -- every gate uses it) are ALSO
untouched: this guard's shape additionally requires the `print(json.dumps(...))`
statement immediately before it, keyed on the SAME parameter the ternary's
`.get("verdict")` reads -- a generic gate's `return 0 if verdict.passed else 1`
never has that paired print statement in the same function, so it is not
this shape.
"""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_DES_CLI = REPO_ROOT / "src" / "des" / "cli"
CANONICAL_MODULE = SRC_DES_CLI / "_scaffold_core.py"


def _is_print_call_of_json_dumps_of(node: ast.stmt, param_name: str) -> bool:
    """True iff `node` is `print(json.dumps(<param_name>))` -- exactly."""
    if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
        return False
    outer = node.value
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


def _is_verdict_ternary_return_of(node: ast.stmt, param_name: str) -> bool:
    """True iff `node` is `return 0 if <param_name>.get("verdict") == <X>
    else 1` -- the exit-code mapping `emit_scaffold_verdict` canonicalizes."""
    if not isinstance(node, ast.Return) or not isinstance(node.value, ast.IfExp):
        return False
    expr = node.value
    if not (
        isinstance(expr.body, ast.Constant)
        and expr.body.value == 0
        and isinstance(expr.orelse, ast.Constant)
        and expr.orelse.value == 1
    ):
        return False
    test = expr.test
    if not isinstance(test, ast.Compare) or len(test.ops) != 1:
        return False
    if not isinstance(test.ops[0], ast.Eq):
        return False
    left = test.left
    return (
        isinstance(left, ast.Call)
        and isinstance(left.func, ast.Attribute)
        and left.func.attr == "get"
        and isinstance(left.func.value, ast.Name)
        and left.func.value.id == param_name
        and len(left.args) >= 1
        and isinstance(left.args[0], ast.Constant)
        and left.args[0].value == "verdict"
    )


def _is_hand_rolled_scaffold_verdict_shape(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    """Property-based: independent of the function's name. True iff `func`
    takes exactly one parameter and its body (docstring aside) is EXACTLY
    `print(json.dumps(<param>))` followed by
    `return 0 if <param>.get("verdict") == <X> else 1`."""
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
    if len(body) != 2:
        return False

    first, second = body
    return _is_print_call_of_json_dumps_of(
        first, param_name
    ) and _is_verdict_ternary_return_of(second, param_name)


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
            if isinstance(
                node, ast.FunctionDef
            ) and _is_hand_rolled_scaffold_verdict_shape(node):
                offenders.append(f"{_display_path(path)}:{node.name}")
    return offenders


def test_no_des_cli_module_reimplements_the_scaffold_verdict_shape():
    offenders = _reimplementations_in(SRC_DES_CLI)
    assert offenders == [], (
        "the following des.cli function(s) reduce to the exact "
        "print(json.dumps(<param>)) + return 0 if <param>.get('verdict') == "
        "X else 1 shape already shared as "
        "des.cli._scaffold_core.emit_scaffold_verdict -- import it instead "
        f"of reimplementing it: {offenders}"
    )


def test_the_guard_spares_the_migrated_scaffold_callers():
    """Locks in that `charter_scaffold` -- which DELEGATES to
    `emit_scaffold_verdict` rather than reimplementing it -- is never flagged. A regression here would mean the guard started
    matching a `return emit_scaffold_verdict(...)` call as if it were the
    reimplemented shape (over-firing), or silently stopped scanning these
    modules at all (under-firing)."""
    offenders = set(_reimplementations_in(SRC_DES_CLI))
    spared = {
        "src/des/cli/charter_scaffold.py:_degrade",
        "src/des/cli/charter_scaffold.py:_emit_single_scaffold_result",
        "src/des/cli/charter_scaffold.py:_run_slice_plan",
    }
    assert offenders & spared == set(), (
        f"the guard flagged migrated (non-reimplementing) caller(s): {offenders & spared}"
    )


def test_the_guard_can_fail(tmp_path: Path):
    """Prove the guard fails for the right reason: plant a fifth copy under a
    NAME the guard has never seen (`_write_verdict`, not `_emit`/`_degrade`)
    in an isolated directory, and watch it go red -- then remove it and
    confirm the same directory goes green again."""
    shadow_dir = tmp_path / "cli"
    shadow_dir.mkdir()
    planted = shadow_dir / "some_new_scaffold.py"
    planted.write_text(
        "import json\n\n\n"
        "def _write_verdict(payload: dict) -> int:\n"
        "    print(json.dumps(payload))\n"
        '    return 0 if payload.get("verdict") == "accepted" else 1\n',
        encoding="utf-8",
    )

    red_offenders = _reimplementations_in(shadow_dir)
    assert any(
        o.endswith("some_new_scaffold.py:_write_verdict") for o in red_offenders
    ), (
        "planting a differently-named fifth copy did not trip the guard -- "
        "it is keying on the function name, not the body shape"
    )

    planted.unlink()
    green_offenders = _reimplementations_in(shadow_dir)
    assert green_offenders == [], (
        "removing the planted copy should clear the guard, and it did not"
    )


def test_the_guard_spares_its_own_canonical_definition():
    """`emit_scaffold_verdict` itself contains the exact shape this guard
    bans everywhere ELSE -- confirm the by-construction exclusion of
    `_scaffold_core.py` actually fires (a definition cannot duplicate
    itself)."""
    offenders = _reimplementations_in(SRC_DES_CLI)
    assert not any("_scaffold_core.py" in offender for offender in offenders), (
        "the canonical module's own definition was flagged -- the "
        "CANONICAL_MODULE exclusion is broken"
    )
