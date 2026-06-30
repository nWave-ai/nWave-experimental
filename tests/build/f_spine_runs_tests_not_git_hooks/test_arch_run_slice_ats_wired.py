"""AT-A1 (slice-04, DDD-1): the slice-AT EXECUTOR is WIRED into the commit path.

Arch-tier, pure-function (no subprocess, no behavioral execution): reads the
shipped ``src/des/cli/__main__.py`` subcommand registry as DATA and asserts the
``run-slice-ats`` subcommand row is present -- the slice executor is reachable
from a registered ``des`` subcommand and is therefore NO LONGER dead code.
Recognized as an arch test (``test_arch_`` prefix under ``tests/build/``) per the
AT-completeness S2 tolerable-variant rule (introspect structure, never exercise
behavior).

Self-application of Principle 13 + the dead-code regression guard (Residuality
seed: "run_slice_ats/executor stays dead code"). The feature exists because
``run_slice_ats`` was BUILT (f-coherence slice-05) and never WIRED -- repo-wide
grep confirmed it had no caller. A future edit that ships the executor module but
forgets the registry row would silently re-open exactly that hole. This test
holds the wiring.

DORMANT-SEAM (D11 / Mandate-15): the net-new load-bearing seam is the WIRING of
the executor into the commit path -- a binding-resolved reach (the registry row
joins the operator-visible ``run-slice-ats`` name to its importable module path).
This witnesses the seam by reading the SAME shipped registry the dispatcher reads
(indirect-wiring counts -- a registry row IS the witnessing, never a naive
name match), asserting the observable effect (the row is present), never a claim
the executor "exists".

ACTIVE-RED (atdd_pure -- NOT @skip): at HEAD ``__main__.py`` registers no
``run-slice-ats`` row (the executor module does not exist yet -- it is built in
slice-01), so the subcommand-name sub-assertion RED-fails with a semantic
AssertionError NAMING the missing row. GREEN once DELIVER ships the executor +
adds the ``run-slice-ats`` registry row (slice-01). The test reads the REAL
shipped file -- a contract over the shipped artifact, not a self-fulfilling
fixture (Mandate-13 protocol-driver).
"""

from __future__ import annotations

import ast
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[3]
_MAIN_PATH = _REPO_ROOT / "src" / "des" / "cli" / "__main__.py"

_EXPECTED_SUBCOMMAND = "run-slice-ats"
_EXPECTED_MODULE = "des.cli.run_slice_ats"


def _registry_rows() -> list[tuple[str, str]]:
    """The (subcommand-name, module-path) pairs in the shipped _REGISTRY, as DATA.

    AST-parses the module and collects every ``_SubcommandRow("name", "module",
    "fn")`` call -- never executes the dispatcher.
    """
    tree = ast.parse(_MAIN_PATH.read_text(encoding="utf-8"))
    rows: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_row = (isinstance(func, ast.Name) and func.id == "_SubcommandRow") or (
            isinstance(func, ast.Attribute) and func.attr == "_SubcommandRow"
        )
        if not is_row or len(node.args) < 2:
            continue
        name_arg, module_arg = node.args[0], node.args[1]
        if isinstance(name_arg, ast.Constant) and isinstance(module_arg, ast.Constant):
            rows.append((str(name_arg.value), str(module_arg.value)))
    return rows


def test_run_slice_ats_subcommand_is_wired() -> None:
    """The ``run-slice-ats`` executor is reachable from a registered subcommand."""
    rows = _registry_rows()
    names = {name for name, _ in rows}
    assert _EXPECTED_SUBCOMMAND in names, (
        f"expected the {_EXPECTED_SUBCOMMAND!r} subcommand WIRED into the "
        f"des dispatcher registry (the slice-AT executor must not be dead code -- "
        f"DDD-1 / AT-A1); registered subcommands: {sorted(names)!r}. The "
        "executor is unwired at HEAD (active-RED)."
    )
    mapped = dict(rows)
    assert mapped.get(_EXPECTED_SUBCOMMAND) == _EXPECTED_MODULE, (
        f"expected {_EXPECTED_SUBCOMMAND!r} to map to {_EXPECTED_MODULE!r}; got "
        f"{mapped.get(_EXPECTED_SUBCOMMAND)!r}."
    )
