"""Layer A arch test (AC-1) -- ban inline des-module interpreter spawns.

Sibling of ``test_no_inline_interpreter_spawn.py``. That test bans a spawn whose
argv[0] is a raw ``sys.executable`` / a bare interpreter literal / an ``os.exec*``
call. This sibling bans the NEXT category: a ``subprocess.*`` spawn whose argv[0]
is a ``python_for(...)`` call AND whose ``-m <module>`` is a ``des`` module (a
literal starting ``des.``), done INLINE -- a sanctioned-interpreter des-module
spawn that forgets to apply ``des_subprocess_env`` and so loses ``des`` from the
child path. A ``-m pytest`` (or any non-``des.`` module) spawn is OUT OF SCOPE per
the feature-delta [REF] Out-of-Scope -- it is a different shape and cannot lose
``des`` from a des-module child path (it spawns pytest, not a des module). E.g.
``verify_environmental_e2e``'s ``-m pytest`` spawn DELIBERATELY isolates
``PYTHONPATH={prefix}`` to run the e2e suite against the INSTALLED package;
routing it through ``des_spawn`` (which prepends the SOURCE des root) would defeat
that isolation, so it is correctly NOT flagged.

Every such site MUST route through ``des.runtime.interpreter.des_spawn`` -- the
centralized helper that applies ``python_for(capability)`` + ``des_subprocess_env``
BY CONSTRUCTION. The single sanctioned exception is ``interpreter.py`` itself (the
helper home, where ``des_spawn`` legitimately calls ``subprocess.run`` with
``python_for(...)`` at argv[0]).

atdd_pure active-RED at HEAD: ~18 inline ``python_for(...)`` spawn sites exist
across ``carpaccio_intercept`` / ``run_contract_gate`` / ``verify_environmental_e2e``
/ ``verify_deliver_entry_contract`` / ``feature_end_cycle_service`` /
``at_review_verdict`` / ``pre_write_handler`` / ``subagent_stop_handler`` /
``pip_target_installer`` / ``perturbation_witness_adapter`` (Tsunami census
2026-06-23). The arch-walk returns a NON-EMPTY violation list -> a real semantic
``AssertionError``, NEVER an import/collection error. GREEN once DELIVER migrates
the last site to ``des_spawn``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DES_ROOT = PROJECT_ROOT / "src" / "des"

# The helper home itself legitimately spawns interpreters with python_for(...)
# at argv[0] (it IS the des_spawn boundary).
SANCTIONED_EXCEPTION = DES_ROOT / "runtime" / "interpreter.py"

# subprocess spawning entry points whose first arg may carry an argv list.
_SUBPROCESS_SPAWNERS = {"run", "Popen", "call", "check_call", "check_output"}


def _des_modules() -> list[Path]:
    """Every ``src/des/**/*.py`` except the sanctioned interpreter helper."""
    modules = sorted(DES_ROOT.rglob("*.py"))
    return [m for m in modules if m != SANCTIONED_EXCEPTION]


def _is_python_for_call(node: ast.expr) -> bool:
    """True iff ``node`` is a ``python_for(...)`` call expression."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "python_for"
    )


def _subprocess_argv_elements(call: ast.Call) -> list[ast.expr] | None:
    """If ``call`` is a ``subprocess.*`` spawner with a non-empty list/tuple first
    argument, return that sequence's element list; otherwise None."""
    func = call.func
    if not (isinstance(func, ast.Attribute) and func.attr in _SUBPROCESS_SPAWNERS):
        return None
    if not (isinstance(func.value, ast.Name) and func.value.id == "subprocess"):
        return None
    if not call.args:
        return None
    first_arg = call.args[0]
    if isinstance(first_arg, (ast.List, ast.Tuple)) and first_arg.elts:
        return list(first_arg.elts)
    return None


def _spawns_des_module(argv: list[ast.expr]) -> bool:
    """True iff ``argv`` is a ``-m <module>`` spawn whose module literal starts
    with ``des.`` -- i.e. a des-module spawn (the AC-1 threat). A ``-m pytest``
    (or any non-``des.`` module) spawn is NOT a des-module spawn and is exempt
    (per feature-delta [REF] Out-of-Scope: pytest spawns are a different shape)."""
    for i, elem in enumerate(argv[:-1]):
        if (
            isinstance(elem, ast.Constant)
            and elem.value == "-m"
            and isinstance(module := argv[i + 1], ast.Constant)
            and isinstance(module.value, str)
            and module.value.startswith("des.")
        ):
            return True
    return False


def _scan_module(path: Path) -> list[str]:
    """Return violation descriptions for one module (empty == clean)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    rel = path.relative_to(PROJECT_ROOT)
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        argv = _subprocess_argv_elements(node)
        if argv is None or not _is_python_for_call(argv[0]):
            continue
        # AC-1 scope: flag ONLY a python_for(...)-interpreter spawn whose `-m`
        # module is a des module. A `-m pytest` / non-des-module spawn is out of
        # the threat model (it cannot lose `des` from a des-module child path)
        # and is exempt.
        if not _spawns_des_module(argv):
            continue
        violations.append(
            f"{rel}:{node.lineno} — inline subprocess spawn of a des module "
            f"with argv[0]=python_for(...); route through "
            f"des.runtime.interpreter.des_spawn(...)"
        )

    return violations


@pytest.mark.fast_gate
def test_no_inline_des_module_spawn_in_des():
    """No ``src/des/**`` module spawns a des-module subprocess inline.

    Every ``subprocess.*`` spawn whose argv[0] is ``python_for(...)`` MUST be
    routed through the centralized ``des_spawn`` helper, so ``des`` is on the
    child path by construction. The only sanctioned inline ``python_for(...)``
    spawn is inside ``src/des/runtime/interpreter.py`` (the ``des_spawn`` home).
    """
    all_violations: list[str] = []
    for module in _des_modules():
        all_violations.extend(_scan_module(module))

    assert not all_violations, (
        "Inline des-module spawn(s) detected in src/des — every subprocess "
        "spawn with a python_for(...) interpreter MUST route through "
        "des.runtime.interpreter.des_spawn(...) so des is on the child "
        "PYTHONPATH by construction:\n  " + "\n  ".join(all_violations)
    )


def test_sanctioned_des_spawn_home_exists():
    """Guards the exception: the helper home must exist, else the ban would
    silently pass by excluding a non-existent path."""
    assert SANCTIONED_EXCEPTION.is_file(), (
        f"sanctioned des_spawn helper home missing: {SANCTIONED_EXCEPTION}"
    )
