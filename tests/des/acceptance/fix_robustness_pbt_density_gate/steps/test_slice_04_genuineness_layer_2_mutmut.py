"""pytest-bdd binding for slice-04-genuineness-layer-2-mutmut.

Thin binding (Mandate-12 / Mandate 10 shared-vocabulary contract): this
module only registers the slice's scenarios and re-exports the shared step
vocabulary from ``common_steps``. No step definitions or business logic
live here.

M2 FIXTURE-ONLY MANDATE (architect, gated not disciplinary per C1): this
binding module and the entire slice-04 AT scope MUST NEVER import
``mutmut`` or subprocess-invoke the ``mutmut`` binary -- else slice-04
inherits the very environment coupling (M2) the gate exists to bound.
The mechanical self-check below (``test_c1_no_live_mutmut_invocation_in_slice_04``)
asserts the discipline statically by AST-walking this very file and the
slice-04 composition layer, per the gate-or-residue policy
(``feedback_gate_or_residue_policy`` STANDING). The check converts the
M2 prose mandate into an executing test.
"""

from __future__ import annotations

import ast
from pathlib import Path

from pytest_bdd import scenarios

from .common_steps import *


scenarios("../slice-04-genuineness-layer-2-mutmut.feature")


# --- C1 mechanical self-check (M2 fixture-only mandate) ----------------------
#
# Per feature-delta §6 slice-04 row + feature-delta §8 gate-or-residue policy
# instantiation: the M2 invariant ("slice-04 ATs MUST NEVER invoke live
# mutmut") is enforced HERE as an executing test, not in prose. Two artefacts
# are statically scanned:
#   1. This binding module (slice-04's only test entry point) -- catches a
#      crafter who adds a live-mutmut probe directly to the AT layer.
#   2. The composition layer (`composition.py`) -- catches a crafter who
#      hides a live-mutmut probe behind a "helper" service method.
# Common-steps is in scope by transitivity (it imports the composition).
#
# The scan walks each artefact's AST and inspects two node classes:
#   * `ast.Import` / `ast.ImportFrom` -- catches `import mutmut`,
#     `from mutmut import X`, `import mutmut as m`.
#   * `ast.Call` to `subprocess.<anything>` -- catches `subprocess.run([...])`,
#     `subprocess.Popen([...])`, `subprocess.check_output([...])`, etc. If
#     any positional/keyword argv literal in the call contains the bare
#     `"mutmut"` string literal as the FIRST argv element (the binary name
#     position), flag it. Bare string mentions of "mutmut" elsewhere in
#     code (docstrings, error messages, comments) are NOT visited because
#     ast.walk skips comments and `ast.Constant` strings in docstring
#     position are ignored when not in a Call.
# This AST-based approach avoids the regex-self-match trap (a regex over
# source text that contains the regex literal `"mutmut"` matches itself).

_SUITE_STEPS_DIR = Path(__file__).resolve().parent

_FORBIDDEN_PATHS_FOR_M2_SCAN: tuple[Path, ...] = (
    Path(__file__).resolve(),  # this binding module
    _SUITE_STEPS_DIR / "composition.py",  # the composition layer
)


def _module_imports_mutmut(tree: ast.AST) -> bool:
    """Return True iff the AST contains any `import mutmut` form.

    Catches `import mutmut`, `import mutmut as m`, `import mutmut.foo`,
    `from mutmut import X`, `from mutmut.foo import Y`.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "mutmut" or alias.name.startswith("mutmut."):
                    return True
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "mutmut" or mod.startswith("mutmut."):
                return True
    return False


def _module_subprocess_invokes_mutmut(tree: ast.AST) -> bool:
    """Return True iff the AST contains a `subprocess.<call>` whose first argv literal is `"mutmut"`.

    Catches `subprocess.run(["mutmut", ...])`,
    `subprocess.Popen(["mutmut", ...])`, `subprocess.check_output(("mutmut", ...))`.

    Bare string mentions of "mutmut" in docstrings, error messages, or
    comments are NOT flagged -- ast.walk does not visit comments, and an
    `ast.Constant("mutmut")` is only inspected when it is the first element
    of a list/tuple passed as the first positional argument of a
    `subprocess.<call>` Call node.

    NAMED RESIDUE: a string built dynamically (e.g. `"mut" + "mut"`) or
    a name reference (`MUTMUT_BIN = "mutmut"; subprocess.run([MUTMUT_BIN])`)
    evades this check. The design accepts the residue per the slice-04 row
    -- the check catches the cheap evasions; the bar can be raised further
    via a repo-wide pre-commit grep if needed.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "subprocess"
        ):
            continue
        if not node.args:
            continue
        first = node.args[0]
        if not isinstance(first, (ast.List, ast.Tuple)):
            continue
        if not first.elts:
            continue
        head = first.elts[0]
        if isinstance(head, ast.Constant) and head.value == "mutmut":
            return True
    return False


def test_c1_no_live_mutmut_invocation_in_slice_04() -> None:
    """Slice-04 AT scope MUST NOT import or subprocess-invoke mutmut.

    Per the M2 architect mandate + C1 gate-or-residue instantiation:
    converting the prose "slice-04 ATs are fixture-driven; live mutmut
    invocation forbidden" into a mechanical check. Two artefacts are
    AST-scanned (this binding + the composition layer); a hit on either
    is a HARD FAIL with a domain-language message naming the offending
    file and pattern.

    NAMED RESIDUE (acceptable, documented): a sufficiently determined
    crafter can hide a live-mutmut probe behind `os.system("mutmut ...")`,
    `__import__("mutmut")`, or string concatenation that builds the
    binary name at runtime. The check catches the cheap evasions; the
    design accepts that the bar can be raised further (e.g. via a
    pre-commit hook that greps the entire suite) but slice-04 ships
    with the in-module AST check as the minimal-effective gate.
    """
    violations: list[str] = []
    for source_path in _FORBIDDEN_PATHS_FOR_M2_SCAN:
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        if _module_imports_mutmut(tree):
            violations.append(
                f"{source_path}: imports `mutmut` (forbidden by M2 -- "
                f"slice-04 ATs MUST use committed fixture mutmut reports)"
            )
        if _module_subprocess_invokes_mutmut(tree):
            violations.append(
                f"{source_path}: subprocess-invokes the mutmut binary "
                f"(forbidden by M2 -- live mutmut invocation re-introduces "
                f"the very environment coupling the gate exists to bound)"
            )
    assert not violations, "\n".join(["M2 fixture-only mandate violated:", *violations])
