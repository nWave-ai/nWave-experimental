"""pytest-bdd configuration for the atdd-spine-ledger-enforcement-gate-v2 AT set.

Slice-00 (kill-switch) scope: isolate environment + filesystem state per test
so AT-1 (env bypass) and AT-2 (file bypass) do not bleed into AT-3 (dormant).

The conftest is placed at the feature root (sibling of the .feature file)
rather than under steps/ -- mirrors the codex-empirical-e2e-support +
fix-hmac-bootstrap-installer precedent and avoids a pytest plugin-name
collision with sibling features that also carry a steps/conftest.py.

RED-for-the-right-reason: the production driving port for slice-00 is the
script `scripts/hooks/spine_ledger_gate.py`. That script does NOT EXIST YET
(slice-04 lands the production wiring per platform architect B3 ordering;
slice-00 only authors ATs + composition). The composition fixture invokes
the target script as a real subprocess (Layer 3); when the script is absent,
subprocess returns exit 2 with a "No such file or directory" stderr and the
fixture surfaces this as AssertionError on the FIRST `Then` step. That is
the correct RED: assertion fires because the implementation is missing.
"""

from __future__ import annotations

import os

import pytest


_BYPASS_ENV = "NWAVE_SPINE_LEDGER_GATE_BYPASS"


@pytest.fixture(autouse=True)
def _isolate_bypass_env() -> object:
    """Restore NWAVE_SPINE_LEDGER_GATE_BYPASS around every test in this suite.

    AT-1 sets the env var; without restoration it leaks into AT-2 and AT-3
    where the absence of the env var is part of the precondition.
    """
    sentinel = object()
    saved = os.environ.get(_BYPASS_ENV, sentinel)
    try:
        yield
    finally:
        if saved is sentinel:
            os.environ.pop(_BYPASS_ENV, None)
        else:
            os.environ[_BYPASS_ENV] = saved  # type: ignore[arg-type]
