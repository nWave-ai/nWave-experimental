"""Tests for the tracked-bytecode guard (scripts/hooks/reject_tracked_bytecode.py).

Regression for `deliver-hook-misses-committed-pyc`: 17 tracked .pyc files landed
across 9 commits though .gitignore forbids them -- no existing pre-commit hook
ever inspected the staged set for gitignore-forbidden bytecode paths. This pins
the pure predicate the hook's `main()` uses to reject such a commit LOUD.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


_HOOK_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "hooks"
    / "reject_tracked_bytecode.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("reject_tracked_bytecode", _HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


_PREDICATE = _load()._is_forbidden_bytecode_path


@pytest.mark.parametrize(
    "path",
    [
        "src/des/domain/foo.pyc",
        "scripts/hooks/bar.pyo",
        "src/des/__pycache__/foo.cpython-312.pyc",
        "__pycache__/module.pyc",
        "nested/dir/__pycache__/x.pyc",
    ],
)
def test_flags_bytecode_paths(path: str) -> None:
    assert _PREDICATE(path) is True


@pytest.mark.parametrize(
    "path",
    [
        "src/des/domain/foo.py",
        "scripts/hooks/reject_tracked_bytecode.py",
        "docs/pycache_explained.md",
        "",
        "src/des/pyconfig.py",
    ],
)
def test_allows_non_bytecode_paths(path: str) -> None:
    assert _PREDICATE(path) is False


def test_main_rejects_when_staged_paths_include_bytecode(monkeypatch) -> None:
    module = _load()
    monkeypatch.setattr(
        module, "_staged_paths", lambda: ["src/des/foo.py", "src/des/foo.pyc"]
    )
    captured: list[str] = []
    monkeypatch.setattr(
        "builtins.print", lambda *a, **k: captured.append(" ".join(map(str, a)))
    )

    exit_code = module.main()

    assert exit_code == 1
    assert any("foo.pyc" in line for line in captured)


def test_main_allows_when_no_bytecode_staged(monkeypatch) -> None:
    module = _load()
    monkeypatch.setattr(
        module, "_staged_paths", lambda: ["src/des/foo.py", "README.md"]
    )

    exit_code = module.main()

    assert exit_code == 0
