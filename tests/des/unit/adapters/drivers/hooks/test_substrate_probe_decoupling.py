"""P1 regression: substrate_probe must be importable without nwave_ai in sys.modules.

Root cause: RC-A (P0-A) — substrate_probe had top-level 'from nwave_ai...' imports.
Standalone DES deployment (des-only PYTHONPATH) would fail at hook import time.

This test prevents recurrence: any future regression that re-introduces a
top-level nwave_ai import into substrate_probe will fail this test immediately.

Test Budget: 1 behavior x 2 = 2 max. Using 1 test.
"""

from __future__ import annotations

import builtins
import importlib
import sys


def test_substrate_probe_importable_without_nwave_ai() -> None:
    """substrate_probe must import successfully even when nwave_ai is absent.

    Simulates a standalone DES deployment where nwave_ai is not on sys.path.
    Uses import-blocking (overriding builtins.__import__) to make nwave_ai
    genuinely unavailable, not merely absent from sys.modules cache.

    Fail-open contract: import must succeed; nwave_ai absence is tolerated.
    """
    # Remove substrate_probe from sys.modules to force fresh import
    modules_to_remove = [key for key in sys.modules if "substrate_probe" in key]
    saved = {key: sys.modules.pop(key) for key in modules_to_remove}

    # Block nwave_ai imports at the builtins level so the module cannot be
    # re-imported even though it is installed in the dev environment.
    orig_import = builtins.__import__

    def _blocking_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "nwave_ai" or name.startswith("nwave_ai."):
            raise ImportError(f"nwave_ai blocked by test: {name}")
        return orig_import(name, *args, **kwargs)  # type: ignore[arg-type]

    builtins.__import__ = _blocking_import  # type: ignore[assignment]
    try:
        # Act: import substrate_probe with nwave_ai genuinely unavailable.
        # Must NOT raise ImportError — fail-open contract requires graceful handling.
        mod = importlib.import_module("des.adapters.drivers.hooks.substrate_probe")
        # Assert: the driving port (run_probe) is callable
        assert callable(getattr(mod, "run_probe", None)), (
            "run_probe not found or not callable on substrate_probe module"
        )
    finally:
        builtins.__import__ = orig_import
        # Restore saved modules
        for key, val in saved.items():
            sys.modules[key] = val
        # Clean up the freshly imported module to avoid test pollution
        for key in list(sys.modules.keys()):
            if "substrate_probe" in key:
                sys.modules.pop(key, None)
