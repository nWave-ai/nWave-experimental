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
the adapter shells out to (``graphify update <root>``) and only the shape
those tests assert on (function-def nodes for ``atoms-in-file``), so the
test environment is deterministic without adding a heavyweight dependency.

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


def _function_nodes(path: Path, relative: str) -> list[dict[str, object]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []
    stem = relative[:-3] if relative.endswith(".py") else relative
    node_prefix = stem.replace("/", "_")
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


def main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[1] != "update":
        print("usage: graphify update <root>", file=sys.stderr)
        return 2
    root = Path(argv[2]).resolve()
    out_dir = root / "graphify-out"
    out_dir.mkdir(parents=True, exist_ok=True)

    nodes: list[dict[str, object]] = []
    manifest: dict[str, dict[str, object]] = {}
    for path in sorted(root.rglob("*.py")):
        if "graphify-out" in path.relative_to(root).parts:
            continue
        relative = path.relative_to(root).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        nodes.extend(_function_nodes(path, relative))
        manifest[relative] = {
            "ast_hash": digest,
            "mtime": path.stat().st_mtime,
            "semantic_hash": digest,
        }

    graph = {
        "nodes": nodes,
        "edges": [],
        "hyperedges": [],
        "input_tokens": 0,
        "output_tokens": 0,
    }
    (out_dir / "graph.json").write_text(json.dumps(graph), encoding="utf-8")
    (out_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
