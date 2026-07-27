"""Regression tests for Python 3.10 compatibility of typing.Self imports.

Issue #43 — `typing.Self` was added in Python 3.11 (PEP 673). Importing it
unconditionally in `value_objects.py` breaks DES on Python 3.10, which is
the documented `requires-python` floor.

value_objects.py no longer duplicates the try/except fallback itself: it
imports `Self` from the single designated locus `des._compat` (which
vendors a stdlib-only fallback for 3.10 -- see ADR-PLAT-007 and
techdebt.md id
`typing-extensions-import-escapes-bundle-stdlib-only-enforcement-gate`),
under an `if TYPE_CHECKING:` guard (ruff TC001 -- `Self` is only ever used
in a `from __future__ import annotations`-deferred annotation, never at
runtime, so it need not be bound at module scope).
These tests are AST-based so they catch the regression statically on any
interpreter (the CI matrix runs 3.11+ today; the static check still works).
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[4] / "src" / "des" / "domain" / "value_objects.py"
)


def _module_ast() -> ast.Module:
    """Parse the value_objects.py module into an AST."""
    source = MODULE_PATH.read_text(encoding="utf-8")
    return ast.parse(source, filename=str(MODULE_PATH))


def _top_level_import_froms(tree: ast.Module) -> list[ast.ImportFrom]:
    """Collect ImportFrom nodes that live directly at module top level
    (i.e. NOT nested inside try/except/if/function/class blocks).
    """
    return [node for node in tree.body if isinstance(node, ast.ImportFrom)]


def _import_froms_in_top_level_type_checking_block(
    tree: ast.Module,
) -> list[ast.ImportFrom]:
    """Collect ImportFrom nodes nested one level inside a top-level
    ``if TYPE_CHECKING:`` guard (ruff TC001's required shape for a
    first-party symbol used only in a deferred annotation).
    """
    found: list[ast.ImportFrom] = []
    for node in tree.body:
        if not isinstance(node, ast.If):
            continue
        test = node.test
        is_type_checking = (
            isinstance(test, ast.Name) and test.id == "TYPE_CHECKING"
        ) or (isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING")
        if not is_type_checking:
            continue
        found.extend(stmt for stmt in node.body if isinstance(stmt, ast.ImportFrom))
    return found


class TestValueObjectsTypingCompat:
    """AST-based regression tests for the typing.Self conditional import."""

    def test_no_bare_typing_self_import(self) -> None:
        """Top-level `from typing import ...` MUST NOT include Self.

        A bare top-level import of `Self` from `typing` breaks Python 3.10.
        The fix imports `Self` from `des._compat` instead, which is a
        top-level ImportFrom of module `des._compat`, not `typing`.
        """
        tree = _module_ast()
        bare_imports = _top_level_import_froms(tree)

        offending = [
            node
            for node in bare_imports
            if node.module == "typing"
            and any(alias.name == "Self" for alias in node.names)
        ]

        assert offending == [], (
            "value_objects.py contains a bare top-level "
            "`from typing import Self` — this fails on Python 3.10. "
            "Import Self from des._compat instead, which handles the "
            "Python-3.10 fallback in one designated, stdlib-only locus."
        )

    def test_self_imported_from_compat_shim(self) -> None:
        """`Self` MUST be imported from the single designated locus
        `des._compat`, never re-implemented with a per-file
        try/except-typing_extensions duplicate (the original defect this
        pins: two independent copies of the same fallback pattern, one of
        which imported a non-stdlib package the bundle-stdlib-only gate
        did not catch).
        """
        tree = _module_ast()
        candidate_imports = _top_level_import_froms(
            tree
        ) + _import_froms_in_top_level_type_checking_block(tree)

        matching = [
            node
            for node in candidate_imports
            if node.module == "des._compat"
            and any(alias.name == "Self" for alias in node.names)
        ]

        assert matching, (
            "value_objects.py must contain a `from des._compat import Self` "
            "(top-level, or inside a top-level `if TYPE_CHECKING:` guard) "
            "-- the designated single locus for the Python-3.10 "
            "typing.Self fallback."
        )

        no_local_typing_extensions_fallback = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == "typing_extensions"
        ]
        assert no_local_typing_extensions_fallback == [], (
            "value_objects.py must not import typing_extensions directly "
            "-- ADR-PLAT-007 requires the bundled DES runtime to depend "
            "on nothing but Python; the Self fallback lives in "
            "des._compat, vendored stdlib-only."
        )

    def test_module_imports_successfully(self) -> None:
        """Importing the module on the running interpreter must succeed
        on every supported Python, regardless of whether `Self` came from
        stdlib `typing` or the vendored `des._compat` fallback.

        `Self` itself is NOT expected to be a runtime module attribute:
        it lives under `if TYPE_CHECKING:` (ruff TC001) because
        `from __future__ import annotations` defers every annotation to a
        string, so the name is never looked up at runtime.
        """
        try:
            importlib.import_module("des.domain.value_objects")
        except ImportError as exc:  # pragma: no cover — diagnostic path
            pytest.fail(f"Failed to import des.domain.value_objects: {exc}")
