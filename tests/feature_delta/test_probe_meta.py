"""
Self-applying meta-test — no orphan adapters (DD-A5).

Introspects nwave_ai/feature_delta/adapters/ and asserts that every
adapter class with a probe() method is covered by test_probes.py.

Behavior: zero orphan adapters detected.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from types import ModuleType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _adapter_classes_with_probe() -> list[tuple[str, str]]:
    """
    Return (module_name, class_name) for every class in
    nwave_ai.feature_delta.adapters that has a probe() method.
    """
    import nwave_ai.feature_delta.adapters as adapters_pkg

    pkg_path = Path(adapters_pkg.__file__).parent
    results: list[tuple[str, str]] = []

    for module_info in pkgutil.iter_modules([str(pkg_path)]):
        mod_name = f"nwave_ai.feature_delta.adapters.{module_info.name}"
        try:
            mod: ModuleType = importlib.import_module(mod_name)
        except ImportError:
            continue
        for name, obj in inspect.getmembers(mod, inspect.isclass):
            if obj.__module__ != mod_name:
                continue  # skip imported classes
            if hasattr(obj, "probe"):
                results.append((mod_name, name))

    return results


def _is_upper_camel_case(name: str) -> bool:
    """Return True for names that look like class names (UpperCamelCase)."""
    return bool(name) and name[0].isupper() and "_" not in name


def _covered_class_names_in_test_probes() -> set[str]:
    """
    Parse test_probes.py with AST and collect class names that are
    instantiated inside test_* method bodies, i.e. appear as:

        var = ClassName(...)   # assignment target in a test function body

    This avoids over-counting Name nodes that appear in monkeypatch calls,
    annotations, or other non-instantiation contexts.
    """
    test_file = Path(__file__).parent / "test_probes.py"
    source = test_file.read_text(encoding="utf-8")
    tree = ast.parse(source)

    covered: set[str] = set()

    for node in ast.walk(tree):
        # Only inspect FunctionDef nodes whose names start with "test_"
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue

        for child in ast.walk(node):
            # Pattern: `target = ClassName(...)` (Assign or AnnAssign)
            if isinstance(child, ast.Assign) or (
                isinstance(child, ast.AnnAssign) and child.value is not None
            ):
                value = child.value
                if (
                    isinstance(value, ast.Call)
                    and isinstance(value.func, ast.Name)
                    and _is_upper_camel_case(value.func.id)
                ):
                    covered.add(value.func.id)

    return covered


# ---------------------------------------------------------------------------
# Meta-test: zero orphan adapters
# ---------------------------------------------------------------------------


class TestProbeMetaOrphanDetection:
    def test_every_adapter_class_is_covered_by_test_probes(self) -> None:
        """Every adapter class with probe() must appear in test_probes.py coverage."""
        adapter_classes = _adapter_classes_with_probe()
        assert adapter_classes, (
            "No adapter classes with probe() found — check adapters package"
        )

        covered = _covered_class_names_in_test_probes()

        orphans = [f"{mod}.{cls}" for mod, cls in adapter_classes if cls not in covered]

        assert not orphans, (
            f"Orphan adapter classes not covered by test_probes.py: {orphans}\n"
            "Add a fault-injection test for each orphan."
        )
