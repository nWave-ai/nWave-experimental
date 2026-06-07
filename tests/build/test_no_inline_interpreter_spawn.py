"""Layer A arch test — the static interpreter-spawn ban (S1, feature-delta §3).

AST-walks every ``src/des/**/*.py`` and FAILS the build if any module spawns a
Python interpreter by a reference other than ``des.runtime.interpreter.python_for``.

The ban covers the *category* "interpreter spawned by a raw reference", not only
the ``sys.executable`` symbol (R-4 widening, residuality amendment):

  (i)   a ``subprocess.run``/``Popen``/``call``/``check_output`` whose first
        list element is ``sys.executable`` (or ``sys.executable`` as an
        ``Attribute``);
  (ii)  a ``subprocess.*`` first-list-element that is a *string literal*
        matching ``^python(3(\\.\\d+)?)?$`` — the exact F-21 bug shape
        (a literal ``["python3", ...]`` argv that a symbol-only ban misses);
  (iii) any ``os.system`` / ``os.popen`` / ``os.exec*`` call — these bypass
        ``subprocess`` entirely and have no sanctioned use in ``src/des``.

This test runs under the dev interpreter (which has pytest) — it proves *no
inline spawn exists in source*. It does NOT prove ``python_for`` resolves a
working interpreter under a pytest-less host: that is Layer B's job
(``test_python_for_under_pytestless_interpreter.py``). A+B is the
non-tautological pair.

The single sanctioned exception is ``src/des/runtime/interpreter.py`` itself —
the helper that legitimately spawns interpreters to probe them.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DES_ROOT = PROJECT_ROOT / "src" / "des"

# The helper itself legitimately spawns interpreters — it is the boundary.
SANCTIONED_EXCEPTION = DES_ROOT / "runtime" / "interpreter.py"

# Bare-name Python interpreter literals: python, python3, python3.12, ...
_INTERPRETER_LITERAL = re.compile(r"^python(3(\.\d+)?)?$")

# subprocess spawning entry points whose first arg may carry an argv list.
_SUBPROCESS_SPAWNERS = {"run", "Popen", "call", "check_call", "check_output"}

# os.* functions that spawn a process outside subprocess.
_OS_EXEC_FUNCS = {
    "system",
    "popen",
    "execl",
    "execle",
    "execlp",
    "execlpe",
    "execv",
    "execve",
    "execvp",
    "execvpe",
}


def _des_modules() -> list[Path]:
    """Every ``src/des/**/*.py`` except the sanctioned interpreter helper."""
    modules = sorted(DES_ROOT.rglob("*.py"))
    return [m for m in modules if m != SANCTIONED_EXCEPTION]


def _is_sys_executable(node: ast.expr) -> bool:
    """True iff ``node`` is the ``sys.executable`` attribute access."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "executable"
        and isinstance(node.value, ast.Name)
        and node.value.id == "sys"
    )


def _is_interpreter_literal(node: ast.expr) -> bool:
    """True iff ``node`` is a bare-name Python interpreter string literal."""
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and bool(_INTERPRETER_LITERAL.match(node.value))
    )


def _subprocess_argv_first_element(call: ast.Call) -> ast.expr | None:
    """If ``call`` is a ``subprocess.*`` spawner with a list first argument,
    return that list's first element; otherwise None."""
    func = call.func
    if not (isinstance(func, ast.Attribute) and func.attr in _SUBPROCESS_SPAWNERS):
        return None
    if not (isinstance(func.value, ast.Name) and func.value.id == "subprocess"):
        return None
    if not call.args:
        return None
    first_arg = call.args[0]
    if isinstance(first_arg, (ast.List, ast.Tuple)) and first_arg.elts:
        return first_arg.elts[0]
    return None


def _is_os_exec_call(call: ast.Call) -> bool:
    """True iff ``call`` is an ``os.system``/``os.popen``/``os.exec*`` call."""
    func = call.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr in _OS_EXEC_FUNCS
        and isinstance(func.value, ast.Name)
        and func.value.id == "os"
    )


def _scan_module(path: Path) -> list[str]:
    """Return a list of violation descriptions for one module (empty == clean)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    rel = path.relative_to(PROJECT_ROOT)
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        first = _subprocess_argv_first_element(node)
        if first is not None:
            if _is_sys_executable(first):
                violations.append(
                    f"{rel}:{node.lineno} — subprocess spawn with raw "
                    f"`sys.executable`; route through python_for(...)"
                )
            elif _is_interpreter_literal(first):
                violations.append(
                    f"{rel}:{node.lineno} — subprocess spawn with string-literal "
                    f"interpreter `{first.value!r}` (F-21 bug shape); "
                    f"route through python_for(...)"
                )

        if _is_os_exec_call(node):
            violations.append(
                f"{rel}:{node.lineno} — os.{node.func.attr} process spawn; "
                f"forbidden in src/des — use subprocess + python_for(...)"
            )

    return violations


@pytest.mark.fast_gate
def test_no_inline_interpreter_spawn_in_des():
    """No ``src/des/**`` module spawns an interpreter by a raw reference.

    The only sanctioned interpreter spawn is inside
    ``src/des/runtime/interpreter.py`` (the probe helper). Every other spawn
    site MUST resolve its interpreter through ``python_for(...)``.
    """
    all_violations: list[str] = []
    for module in _des_modules():
        all_violations.extend(_scan_module(module))

    assert not all_violations, (
        "Inline interpreter spawn(s) detected in src/des — every Python "
        "interpreter spawn MUST route through "
        "des.runtime.interpreter.python_for(...):\n  " + "\n  ".join(all_violations)
    )


def test_sanctioned_exception_exists():
    """Guards the exception itself: the helper file must exist, else the ban
    would silently pass by excluding a non-existent path."""
    assert SANCTIONED_EXCEPTION.is_file(), (
        f"sanctioned interpreter helper missing: {SANCTIONED_EXCEPTION}"
    )
