"""No DES-plugin tree copy may carry a bytecode cache.

``__pycache__`` is a build artefact, not module surface, and copying it is not
merely wasteful: a live interpreter writes ``.pyc`` through a temporary file it
renames into place, so a copy that walks that directory can see a name that no
longer exists a moment later and die with FileNotFoundError mid-install.

Two of the plugin's copies already passed ``ignore``; the rest did not, which is
why the race kept surviving its own fix. The invariant is checked structurally
so a NEW copytree cannot reintroduce it unnoticed.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


PLUGIN = (
    Path(__file__).resolve().parents[3]
    / "scripts"
    / "install"
    / "plugins"
    / "des_plugin.py"
)


def _copytree_calls() -> list[ast.Call]:
    tree = ast.parse(PLUGIN.read_text(encoding="utf-8"))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "copytree"
    ]


def test_the_plugin_actually_copies_trees() -> None:
    """Guards the scan: zero matches would make the invariant vacuous."""
    assert _copytree_calls()


@pytest.mark.parametrize("call", _copytree_calls(), ids=lambda c: f"line-{c.lineno}")
def test_every_copytree_ignores_bytecode_caches(call: ast.Call) -> None:
    ignore = next((kw for kw in call.keywords if kw.arg == "ignore"), None)
    assert ignore is not None, (
        f"shutil.copytree at des_plugin.py:{call.lineno} passes no ignore=, so it "
        "will walk __pycache__ and can race a concurrent .pyc write"
    )

    ignored = {
        arg.value
        for arg in getattr(ignore.value, "args", [])
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
    }
    assert "__pycache__" in ignored, (
        f"shutil.copytree at des_plugin.py:{call.lineno} has an ignore= that does "
        f"not exclude __pycache__ (excludes: {sorted(ignored)})"
    )
