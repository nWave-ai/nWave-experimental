"""Verify a DeliveryContract target's ``declared-imports`` name a real symbol.

K4 failure-to-design matrix row 12 (``docs/analysis/2026-08-05-des-simplification-
evidence-backed-roadmap.md``): an ATD subject invented ``declared-imports`` that
named symbols absent from the base tree. ``thin-delivery-contract.schema.json``
already requires the field; this resolver closes the remaining semantic gap —
existence in the base tree — with Python-only means (AST, with a same-file text
fallback), never by importing or executing the referenced module.

Scope: ``declared-imports`` is deliberately language-agnostic (npm ``@scope/pkg``,
Rust ``crate::module``, ...) so a non-Python-shaped reference (containing ``::``,
``/`` or a leading ``@``) is outside this checker's competence and is treated as
unverifiable-here, never as a false rejection. Every real checked-in
``docs/delivery-contracts/*.json`` reference is Python dotted notation, matching
ADR-PLAT-001's Python-only runtime dependency.

Resolution walks the LONGEST module prefix that resolves to a real file, then
verifies the remaining attribute chain structurally: module-level lookups
reuse the shared ``PythonAstAdapter`` (``des.testarch.adapters.python_ast``,
ADR-LA-001 R15 -- one parser, no drifting second walk) for
``module_level_symbols_in_module``/``module_level_assignment_targets_in_module``;
a nested class body has no port coverage (the adapter deliberately never
walks into or exposes a class member -- ``functions_in_module`` is the only
below-module-level surface it offers, and it is unfiltered/nameless), so
descent below the module uses a small dedicated AST walk. Whenever the chain
cannot be structurally decided (attribute access beyond a function/variable/
import -- a dynamically-assigned attribute no static walk can rule out), this
resolves NOT-DECIDABLE, i.e. ``True``: a validator must never false-reject.
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING

from des.testarch.adapters.python_ast import PythonAstAdapter


if TYPE_CHECKING:
    from pathlib import Path


_NON_PYTHON_SHAPE = re.compile(r"::|/|^@")
#: `src/des` ships as `des` (pyproject.toml build flattening); other packages
#: (`scripts`, `nwave_ai`, ...) sit directly at the repository root.
_SEARCH_PREFIXES = ("src", "")

#: Sentinel: the chain segment resolved to a real module-/class-level member
#: that is NOT a class (a function, an assignment target, an import alias) --
#: found, but there is no `.body` to descend into for a further segment.
_LEAF = object()

_parser = PythonAstAdapter()


def _candidate_roots(repo_root: Path) -> tuple[Path, ...]:
    return tuple(
        (repo_root / prefix) if prefix else repo_root for prefix in _SEARCH_PREFIXES
    )


def _module_file(root: Path, segments: tuple[str, ...]) -> Path | None:
    as_module = root.joinpath(*segments).with_suffix(".py")
    if as_module.is_file():
        return as_module
    as_package = root.joinpath(*segments, "__init__.py")
    if as_package.is_file():
        return as_package
    return None


def _longest_module_prefix(
    root: Path, segments: tuple[str, ...]
) -> tuple[Path, tuple[str, ...]] | None:
    """The longest leading slice of `segments` that resolves to a real module
    file, paired with the remaining (possibly empty) attribute chain."""
    for split in range(len(segments), 0, -1):
        module_file = _module_file(root, segments[:split])
        if module_file is not None:
            return module_file, segments[split:]
    return None


def _import_alias_at_top(body: list[ast.stmt], name: str) -> bool:
    for node in body:
        if isinstance(node, (ast.Import, ast.ImportFrom)) and any(
            (alias.asname or alias.name) == name for alias in node.names
        ):
            return True
    return False


def _module_level_lookup(
    module_tree: ast.Module, name: str
) -> ast.ClassDef | object | None:
    """Resolve `name` at MODULE level via the shared `PythonAstAdapter`
    (ADR-LA-001 R15): a class returns its live node (needed to descend
    further); a function/assignment/import returns `_LEAF`; absent is
    `None`."""
    for symbol in _parser.module_level_symbols_in_module(module_tree):
        if symbol.name != name:
            continue
        if symbol.kind != "class":
            return _LEAF
        return next(
            (
                node
                for node in module_tree.body
                if isinstance(node, ast.ClassDef) and node.name == name
            ),
            _LEAF,
        )
    if name in _parser.module_level_assignment_targets_in_module(module_tree):
        return _LEAF
    if _import_alias_at_top(module_tree.body, name):
        return _LEAF
    return None


def _class_level_lookup(
    class_node: ast.ClassDef, name: str
) -> ast.ClassDef | object | None:
    """Resolve `name` among `class_node`'s own body members. No port covers
    class-member introspection (`PythonAstAdapter` is module-level-only by
    design), so this is a small dedicated AST walk."""
    for node in class_node.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == name
        ):
            return _LEAF
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            return _LEAF
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
        ):
            return _LEAF
    return None


def _attribute_chain_resolves(module_file: Path, chain: tuple[str, ...]) -> bool:
    """Walk `chain` from `module_file`'s top level, descending into a class
    body per segment. Returns `True` on a found leaf/class, on a
    not-statically-decidable step (never a false rejection), or on an
    unreadable/unparseable file (cannot prove absence); `False` only when a
    segment is genuinely absent everywhere in the file."""
    try:
        source = module_file.read_text(encoding="utf-8")
        tree = _parser.parse(source, str(module_file))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return True
    assert isinstance(tree, ast.Module)

    container: ast.Module | ast.ClassDef = tree
    for index, name in enumerate(chain):
        found = (
            _module_level_lookup(container, name)
            if isinstance(container, ast.Module)
            else _class_level_lookup(container, name)
        )
        if found is None:
            return re.search(rf"\b{re.escape(name)}\b", source) is not None
        if index == len(chain) - 1:
            return True
        if found is _LEAF:
            return True  # attribute access beyond a def/variable/import: dynamic, not decidable
        container = found

    return True


def resolve_declared_import(repo_root: Path, reference: str) -> bool:
    """Return ``True`` when ``reference`` names a real base-tree symbol.

    A non-Python-shaped reference is outside this checker's competence and
    returns ``True`` (unverifiable-here is never a false rejection).
    """
    if _NON_PYTHON_SHAPE.search(reference):
        return True

    dotted = reference.removeprefix("@")
    segments = tuple(dotted.split("."))
    if not segments or not all(segments):
        return False

    for root in _candidate_roots(repo_root):
        located = _longest_module_prefix(root, segments)
        if located is None:
            continue
        module_file, remaining = located
        if not remaining:
            return True
        if _attribute_chain_resolves(module_file, remaining):
            return True

    return False
