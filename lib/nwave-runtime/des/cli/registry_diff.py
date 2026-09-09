"""Diff `des`'s subcommand registry between an old installed tree and a new
one about to replace it (F-INSTALL-REMOVAL-TRANSPARENCY).

RCA (docs/product/backlog.md:1327): no point of the installer ever diffed
``_REGISTRY``'s name set between an old install and a new one -- the
filesystem-sweep mechanisms (``sweep_retired_assets``) delete named FILES
one-per-line and do not apply here, because ``_REGISTRY`` rows are Python
source inside ONE file that travels whole via ``shutil.copytree``.

Everything here is a pure, side-effect-free reader over source text. It
never imports or executes the file it reads: the old tree may belong to a
different, unknown-compatible Python/des version, so importing it would be
both a portability and a safety violation (ADR-PLAT-001, pure-Python-only
extends to "never exec a foreign version's code to describe it").
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


def _parse_or_none(path: Path) -> ast.Module | None:
    """Read and AST-parse *path*, ``None`` on any I/O or syntax failure.

    Shared by every reader in this module -- never imports or executes the
    file, so a foreign-version tree or a mid-edit syntax error degrades to
    "no fact", never a crash or a fabricated one.
    """
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


def registry_names_from_source(path: Path) -> frozenset[str] | None:
    """Extract every ``_SubcommandRow(...)`` first-argument name via a
    static AST parse of *path*.

    Returns ``None`` (fail-open: no diff rather than a fabricated one) when
    the file is missing, unreadable, or does not parse as Python.
    """
    tree = _parse_or_none(path)
    if tree is None:
        return None

    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        func_name = func.id if isinstance(func, ast.Name) else None
        if func_name != "_SubcommandRow":
            continue
        if not node.args:
            continue
        first_arg = node.args[0]
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            names.add(first_arg.value)

    return frozenset(names)
