"""Regression + prevention guard: conftest/test module names must be globally unique.

Repo runs pytest under ``--import-mode=importlib`` AND
``consider_namespace_packages = true`` (both in pyproject.toml). Under a plain
``__init__.py``-chain resolution, walking the chain and re-rooting at the first
non-identifier (hyphenated) directory makes two distinct trees derive the *same*
truncated module name (``steps.conftest`` / ``acceptance.steps.conftest``), which
would make pluggy abort collection with::

    ValueError: Plugin already registered under a different name

``consider_namespace_packages = true`` is precisely what prevents that abort: it
anchors every module at its full rootdir-relative path, so the derived names stay
globally unique even across hyphenated feature trees.

This guard enumerates every ``conftest.py`` and test module under ``tests/``,
derives the importlib module name **the way pytest actually does** (i.e. WITH
``consider_namespace_packages=True``, mirroring the ini), and asserts the derived
names are globally unique. It is both the regression test for the
``acceptance.steps.conftest`` collision (PR #37) and the standing P2 prevention
guard against any future duplicate that would survive the namespace-package
anchoring.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from _pytest.pathlib import (
    CouldNotResolvePathError,
    module_name_from_path,
    resolve_pkg_root_and_module_name,
)


TESTS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TESTS_ROOT.parent


def _collected_module_files() -> list[Path]:
    """Every conftest.py and test module pytest would import under tests/."""
    conftests = TESTS_ROOT.rglob("conftest.py")
    test_modules = TESTS_ROOT.rglob("test_*.py")
    paths = {
        path.resolve()
        for path in (*conftests, *test_modules)
        if "__pycache__" not in path.parts
    }
    return sorted(paths)


def _derived_module_name(path: Path) -> str:
    """Module name pytest derives under --import-mode=importlib.

    Mirrors ``_pytest.pathlib.import_path``'s importlib branch: first try the
    ``__init__.py``-chain resolution, on ``CouldNotResolvePathError`` fall back
    to the unique path-based name pytest uses for rootless modules.

    ``consider_namespace_packages=True`` MUST be passed because the repo sets
    ``consider_namespace_packages = true`` in ``pyproject.toml`` (the
    ``[tool.pytest.ini_options]`` block). pytest reads that ini option and
    threads it into ``import_path`` -> ``resolve_pkg_root_and_module_name``
    during real collection, so the faithful reproduction of the names pytest
    actually derives MUST mirror it. Under namespace-package resolution each
    module is anchored at its full rootdir-relative path (e.g.
    ``tests.des.acceptance.<feature>.steps.conftest``) rather than truncated to
    a bare ``steps.conftest`` / ``acceptance.steps.conftest`` -- which is
    exactly why actual collection of the hyphenated feature trees does not
    abort with "Plugin already registered under a different name". Omitting it
    would model a default-False collision that real collection never hits (a
    false positive).
    """
    try:
        _root, module_name = resolve_pkg_root_and_module_name(
            path, consider_namespace_packages=True
        )
    except CouldNotResolvePathError:
        return module_name_from_path(path, REPO_ROOT)
    return module_name


def test_derived_module_names_are_globally_unique() -> None:
    names_to_paths: dict[str, list[Path]] = defaultdict(list)
    for path in _collected_module_files():
        names_to_paths[_derived_module_name(path)].append(path)

    collisions = {
        name: paths for name, paths in names_to_paths.items() if len(paths) > 1
    }

    assert not collisions, "Duplicate pytest-derived module names: " + "; ".join(
        f"{name} <- [{', '.join(str(p.relative_to(TESTS_ROOT)) for p in paths)}]"
        for name, paths in sorted(collisions.items())
    )
