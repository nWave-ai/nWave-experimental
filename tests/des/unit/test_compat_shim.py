"""Regression tests for the typing-compat shim and ruff target-version pin.

Issue #43 — HARDENING layer per RCA. Two complementary defenses against
typing-version regressions:

1. ``src/des/_compat.py`` — designated location for typing-3.11+ symbols,
   backed on Python 3.10 by a vendored, stdlib-only shim (NOT
   ``typing_extensions`` -- see ADR-PLAT-007 and techdebt.md id
   ``typing-extensions-import-escapes-bundle-stdlib-only-enforcement-gate``:
   the bundled DES runtime must depend on nothing but Python on the
   target machine).
2. ``[tool.ruff] target-version = "py310"`` — makes ruff statically flag
   3.11+-only typing imports as ``UP`` errors at lint time, before merge.

These tests are the regression net: they fail the moment either defense
is removed or weakened.
"""

from __future__ import annotations

import importlib
import sys
import typing
from pathlib import Path

import pytest


try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]  # Python 3.10 fallback


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_compat_shim_exports_self() -> None:
    """The ``_compat`` shim must export ``Self`` on every supported Python."""
    from des._compat import Self

    assert Self is not None, "Self must be importable from des._compat"

    if sys.version_info >= (3, 11):
        assert Self is typing.Self, (
            "On Python 3.11+, des._compat.Self must be the stdlib typing.Self"
        )
    else:  # pragma: no cover — only hit on Python 3.10
        assert Self is not None
        with pytest.raises(TypeError):
            Self[int]  # the vendored fallback must reject subscripting


def test_compat_shim_self_fallback_does_not_require_typing_extensions() -> None:
    """The Python-3.10 fallback branch must work with NO ``typing_extensions``
    installed at all -- the exact defect this regression pins: ADR-PLAT-007
    requires the bundled DES runtime to depend on nothing but Python, so the
    fallback for ``Self`` must be vendored stdlib-only, never a second
    package import.

    Simulates a bare Python 3.10 target by monkeypatching ``sys.version_info``
    to ``(3, 10, 0, "final", 0)`` (the runtime discriminant ``_compat.py``'s
    ``elif sys.version_info >= (3, 11)`` branch actually checks) AND blocking
    ``typing_extensions`` from importing at all (``sys.modules
    ['typing_extensions'] = None`` makes any ``import typing_extensions``
    raise ImportError) -- then reloads ``des._compat`` and asserts it still
    succeeds.
    """
    import des._compat as compat

    original_version_info = sys.version_info
    original_typing_extensions = sys.modules.get("typing_extensions")

    sys.version_info = (3, 10, 0, "final", 0)  # type: ignore[assignment]
    sys.modules["typing_extensions"] = None  # type: ignore[assignment]

    try:
        reloaded = importlib.reload(compat)
        assert hasattr(reloaded, "Self"), (
            "des._compat must still export Self on a simulated Python 3.10 "
            "target even when typing_extensions cannot be imported at all"
        )
        with pytest.raises(TypeError):
            reloaded.Self[int]  # the vendored fallback must reject subscripting
    finally:
        sys.version_info = original_version_info  # type: ignore[assignment]
        if original_typing_extensions is not None:
            sys.modules["typing_extensions"] = original_typing_extensions
        else:
            sys.modules.pop("typing_extensions", None)
        importlib.reload(compat)


def test_compat_shim_advertises_self_in_dunder_all() -> None:
    """``__all__`` must list ``Self`` so star-imports stay explicit."""
    import des._compat as compat

    assert hasattr(compat, "__all__"), "des._compat must define __all__"
    assert "Self" in compat.__all__, "Self must be advertised in __all__"


def test_ruff_target_version_is_py310() -> None:
    """``[tool.ruff] target-version`` must be pinned to ``py310``.

    This pin makes ruff fail-fast on bare ``from typing import Self`` (and
    other 3.11+-only symbols) before they reach CI on Python 3.10 runners.
    """
    pyproject = REPO_ROOT / "pyproject.toml"
    assert pyproject.is_file(), f"pyproject.toml not found at {pyproject}"

    with pyproject.open("rb") as handle:
        config = tomllib.load(handle)

    ruff_section = config.get("tool", {}).get("ruff", {})
    target_version = ruff_section.get("target-version")

    assert target_version == "py310", (
        f"[tool.ruff] target-version must be 'py310' to catch 3.11+ "
        f"typing imports at lint time; got {target_version!r}"
    )
