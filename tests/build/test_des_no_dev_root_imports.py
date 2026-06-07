"""S2 arch test — ``des.*`` must not import ``scripts.*`` / ``tests.*``
(feature-delta §4, the F-19 class).

``scripts/`` and ``tests/`` are present in the dev checkout (importable) and
**absent** from the installed ``des`` package. Any ``from scripts...`` /
``import scripts`` / ``from tests...`` in shipped ``src/des`` code is a
load-time ``ImportError`` on the target machine.

AST-walks every ``src/des/**/*.py`` and FAILS on any ``Import``/``ImportFrom``
whose root module is ``scripts`` or ``tests``. Static-only is sufficient: an
import statement's presence in source IS the defect (unlike F-21, where
presence-in-source and runtime behaviour diverge — no behavioural layer needed).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DES_ROOT = PROJECT_ROOT / "src" / "des"

# Roots that exist in the dev checkout but not in the installed des package.
FORBIDDEN_ROOTS = {"scripts", "tests"}


def _des_modules() -> list[Path]:
    """Every ``src/des/**/*.py``."""
    return sorted(DES_ROOT.rglob("*.py"))


def _root_module(dotted: str) -> str:
    """First segment of a dotted module path (``scripts.foo.bar`` -> ``scripts``)."""
    return dotted.split(".", 1)[0]


def _scan_module(path: Path) -> list[str]:
    """Return violation descriptions for one module (empty == clean)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    rel = path.relative_to(PROJECT_ROOT)
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _root_module(alias.name) in FORBIDDEN_ROOTS:
                    violations.append(
                        f"{rel}:{node.lineno} — `import {alias.name}` "
                        f"(dev-root import, absent in installed des package)"
                    )
        elif isinstance(node, ast.ImportFrom):
            # node.level > 0 is a relative import — always within des, never
            # a dev-root. node.module is None only for bare relative imports.
            if node.level == 0 and node.module:
                if _root_module(node.module) in FORBIDDEN_ROOTS:
                    violations.append(
                        f"{rel}:{node.lineno} — `from {node.module} import ...` "
                        f"(dev-root import, absent in installed des package)"
                    )

    return violations


@pytest.mark.fast_gate
def test_des_has_no_dev_root_imports():
    """No ``src/des/**`` module imports ``scripts.*`` or ``tests.*``.

    Such imports load fine in the dev checkout but raise ``ImportError`` on the
    target machine where only the ``des`` package ships.
    """
    all_violations: list[str] = []
    for module in _des_modules():
        all_violations.extend(_scan_module(module))

    assert not all_violations, (
        "Dev-root import(s) detected in src/des — `scripts` and `tests` are "
        "absent from the installed des package and will raise ImportError on "
        "the target machine:\n  " + "\n  ".join(all_violations)
    )
