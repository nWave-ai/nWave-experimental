"""Shared pytest-bdd ``scenarios()`` binding detection (AST, stdlib only).

Single-locus extraction (bug #64, twin of #29/#42): both
:func:`des.cli.verify_negative_at._module_level_scenarios_call` and
:func:`des.cli.carpaccio_format.count_pytest_regression_ats` need to
recognize a module-level ``pytest_bdd.scenarios(<literal>)`` binding --
either the imported-name form (``from pytest_bdd import scenarios``) or the
attribute form (``pytest_bdd.scenarios(...)``). pytest-bdd registers its
tests dynamically at collection time, so a static AST walk over literal
``def test_*`` functions never sees them; a caller that only counts
``def test_*`` misreports a valid gherkin-bound shim as empty/malformed.

Python + stdlib only; no test execution, no external tools.
"""

from __future__ import annotations

import ast


def module_level_scenarios_call(tree: ast.Module) -> ast.Call | None:
    """A module-level ``pytest_bdd.scenarios(<literal>)`` call, if present --
    either the imported-name form (``from pytest_bdd import scenarios``) or
    the attribute form (``pytest_bdd.scenarios(...)``). Only the first
    positional argument is inspected (the minimal, well-known shape); a
    non-literal or missing first argument does not match."""
    for node in tree.body:
        call = node.value if isinstance(node, ast.Expr) else None
        if not isinstance(call, ast.Call):
            continue
        func = call.func
        if isinstance(func, ast.Attribute):
            name = func.attr
        elif isinstance(func, ast.Name):
            name = func.id
        else:
            name = None
        if name != "scenarios" or not call.args:
            continue
        first_arg = call.args[0]
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            return call
    return None
