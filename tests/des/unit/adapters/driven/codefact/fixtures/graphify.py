#!/usr/bin/env python3
"""Shared logic AND module identity for the deterministic, bounded stand-in
for the real ``graphify`` CLI (see the extensionless ``graphify`` POSIX
wrapper in this same directory, which imports :func:`main` from here).

This repo's Portability rule (CLAUDE.md) keeps the real ``graphify`` tool
optional -- ``GraphifyAdapter`` never depends on it at runtime, and CI does
not install it. The synchronous-regeneration tests in this same directory
(``test_graphify_stale_graph_should_regenerate_not_degrade.py``,
``test_graphify_concurrent_synchronous_regeneration_is_safe.py``) need a
REAL executable named ``graphify`` on ``PATH`` to exercise the adapter's
``shutil.which`` + ``subprocess`` regeneration path end to end; installing
the actual npm/pip tool as a CI dependency would make Graphify a runtime
requirement it is not. This module implements exactly the one subcommand
the adapter shells out to (``graphify update <root>``), so the test
environment is deterministic without adding a heavyweight dependency.

Because CI installs no real graphify, this module is the ONLY producer of
a materialized index in this repo -- so it emits the axes a consumer
actually discriminates on, not just nodes: function-def nodes (for
``atoms-in-file``) AND ``calls``/``imports`` edges carrying the real
graph's already-recorded field set (``source``, ``target``, ``relation``,
``confidence``, ``source_file``, ``source_location``) at ``EXTRACTED``
confidence (for ``callers-of``/``never-wired``). No new edge vocabulary
is invented here; a consumer's relation/confidence filtering is therefore
observable against data that really carries more than one relation.

Named ``graphify.py`` (rather than a private ``_graphify_logic.py``) so
``shutil.which("graphify")`` can resolve it DIRECTLY on Windows once the
test fixture prepends ``.PY`` to ``PATHEXT`` -- Windows has no kernel-level
shebang mechanism and ``shutil.which`` there only matches ``PATHEXT``
extensions, so an extensionless file (this directory's POSIX ``graphify``
wrapper) is not a reliable cross-platform target. ``GraphifyAdapter``'s own
spawn construction (``graphify_code_fact_adapter.py:_run_graphify_update``)
launches a resolved ``.py`` executable via ``[sys.executable, executable,
...]`` rather than executing it directly, which is what makes this single
module launchable on both platforms without a second, duplicated ``.cmd``/
``.bat`` shim -- CLAUDE.md's Portability rule forbids shell/batch scripts
in this repo outright.
"""

from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path


def _parse(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None


def _node_prefix(relative: str) -> str:
    stem = relative[:-3] if relative.endswith(".py") else relative
    return stem.replace("/", "_")


def _function_nodes(tree: ast.Module, relative: str) -> list[dict[str, object]]:
    node_prefix = _node_prefix(relative)
    return [
        {
            "id": f"{node_prefix}_{node.name}",
            "label": node.name,
            "source_file": relative,
            "source_location": f"L{node.lineno}",
            "file_type": "code",
        }
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def _called_name(func: ast.expr) -> str:
    """The trailing callable name of a call site's ``func`` expression --
    ``target()`` and ``owner.target()`` both name ``target`` (the real
    graph resolves a ``calls`` edge by TARGET NODE, not by call syntax)."""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _imported_names(node: ast.stmt) -> list[str]:
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return [
            alias.asname or alias.name.rsplit(".", maxsplit=1)[-1]
            for alias in node.names
        ]
    return []


def _edges(
    tree: ast.Module, relative: str, ids_by_label: dict[str, str]
) -> list[dict[str, object]]:
    """Second-pass edge extraction against the SCOPE-WIDE def index.

    A call site's target is frequently defined in ANOTHER file, so the
    label index must be complete before any edge can be resolved -- hence
    two passes over the same parsed trees, not a widened single pass.

    Both ``calls`` and ``imports`` edges are emitted, at the real graph's
    recorded ``EXTRACTED`` confidence and field set: a consumer that
    discriminates on the ``relation`` axis (``GraphifyAdapter`` counts
    ``calls`` edges ONLY) is then discriminating against data that really
    carries both relations, not against a shape fitted to it.
    """
    source_id = _node_prefix(relative)
    edges: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            label = _called_name(node.func)
            target = ids_by_label.get(label)
            if target is not None:
                edges.append(
                    {
                        "source": source_id,
                        "target": target,
                        "relation": "calls",
                        "confidence": "EXTRACTED",
                        "source_file": relative,
                        "source_location": f"L{node.lineno}",
                    }
                )
            continue
        for label in _imported_names(node):
            target = ids_by_label.get(label)
            if target is not None:
                edges.append(
                    {
                        "source": source_id,
                        "target": target,
                        "relation": "imports",
                        "confidence": "EXTRACTED",
                        "source_file": relative,
                        "source_location": f"L{node.lineno}",
                    }
                )
    return edges


def main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[1] != "update":
        print("usage: graphify update <root>", file=sys.stderr)
        return 2
    root = Path(argv[2]).resolve()
    out_dir = root / "graphify-out"
    out_dir.mkdir(parents=True, exist_ok=True)

    nodes: list[dict[str, object]] = []
    manifest: dict[str, dict[str, object]] = {}
    parsed: list[tuple[str, ast.Module]] = []
    for path in sorted(root.rglob("*.py")):
        if "graphify-out" in path.relative_to(root).parts:
            continue
        relative = path.relative_to(root).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        tree = _parse(path)
        if tree is not None:
            parsed.append((relative, tree))
            nodes.extend(_function_nodes(tree, relative))
        manifest[relative] = {
            "ast_hash": digest,
            "mtime": path.stat().st_mtime,
            "semantic_hash": digest,
        }

    ids_by_label = {
        str(node["label"]): str(node["id"])
        for node in nodes
        if node.get("label") and node.get("id")
    }
    edges: list[dict[str, object]] = []
    for relative, tree in parsed:
        edges.extend(_edges(tree, relative, ids_by_label))

    graph = {
        "nodes": nodes,
        "edges": edges,
        "hyperedges": [],
        "input_tokens": 0,
        "output_tokens": 0,
    }
    (out_dir / "graph.json").write_text(json.dumps(graph), encoding="utf-8")
    (out_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
