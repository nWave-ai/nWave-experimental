"""
AST walker: enforce probe() presence on all adapter classes (DD-A5 structural layer).

Walks nwave_ai/feature_delta/adapters/*.py, finds every class definition,
and fails with exit 1 if any class lacks a probe() method definition.

This is the structural enforcement layer (layer 2 of 3):
  1. Subtype   — ClockPort Protocol includes probe(); mypy strict catches missing.
  2. Structural — this AST walker (pre-commit + CI).
  3. Behavioral — tests/feature_delta/test_probes.py fault injection.

Usage (pre-commit):
  python scripts/hooks/check_probe_method.py [file ...]

Exit codes:
  0 — all adapter classes have probe()
  1 — one or more adapter classes are missing probe()
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


# Classes that are intentionally exempt (e.g. exception classes, mix-ins, helpers).
# Exception subclasses that live in adapter modules are not adapter implementations
# and must not be required to implement probe().
_EXEMPT_CLASSES: frozenset[str] = frozenset(
    {
        "ReDoSError",  # Custom ValueError subclass in verbs.py — not an adapter.
    }
)

# Default adapter package location relative to repo root.
_DEFAULT_ADAPTERS_DIR = (
    Path(__file__).parent.parent.parent / "nwave_ai" / "feature_delta" / "adapters"
)


def _has_probe_method(class_node: ast.ClassDef) -> bool:
    """Return True if the class body contains a def probe(...) method."""
    for node in class_node.body:
        if isinstance(node, ast.FunctionDef) and node.name == "probe":
            return True
    return False


def _check_file(path: Path) -> list[str]:
    """
    Parse `path` and return violation messages for classes missing probe().

    Returns an empty list when all classes are compliant.
    """
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [f"{path}: SyntaxError — {exc}"]

    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if node.name in _EXEMPT_CLASSES:
            continue
        if not _has_probe_method(node):
            violations.append(
                f"{path}:{node.lineno}: class '{node.name}' is missing probe() method. "
                f"DD-A5 requires every driven adapter to implement probe(self) -> None."
            )
    return violations


def _collect_adapter_files(paths: list[str]) -> list[Path]:
    """
    Resolve the list of files to check.

    If `paths` is provided (pre-commit passes staged files), filter to
    adapter files only.  Otherwise scan the default adapters directory.
    """
    if paths:
        return [
            Path(p)
            for p in paths
            if Path(p).suffix == ".py" and "adapters" in p and Path(p).exists()
        ]
    return sorted(_DEFAULT_ADAPTERS_DIR.glob("*.py"))


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    files = _collect_adapter_files(args)

    all_violations: list[str] = []
    for path in files:
        if path.name == "__init__.py":
            continue
        all_violations.extend(_check_file(path))

    if all_violations:
        for msg in all_violations:
            print(msg, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
