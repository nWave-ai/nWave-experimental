"""pytest-bdd configuration for the pista1v2-phase225-bypasscause AT set.

Slice-01 (BypassCause StrEnum extraction) scope: the AT-1 parity outline drives
the spine-ledger gate subprocess across five cause branches; AT-1's env-bypass
case sets `NWAVE_SPINE_LEDGER_GATE_BYPASS=1` and without per-test restoration
the env-var would leak into the dormant + block branches of the SAME parametrized
outline. The autouse fixture mirrors the predecessor-feature isolation contract
(see `tests/installer/acceptance/atdd-spine-ledger-enforcement-gate-v2/conftest.py`).

Placement: at the feature root (sibling of the .feature file), NOT under steps/.
This mirrors the codex-empirical-e2e-support / fix-hmac-bootstrap-installer /
atdd-spine-ledger-enforcement-gate-v2 precedent and avoids a pytest plugin-name
collision with sibling features that also carry a steps/conftest.py.

RED-for-the-right-reason: the production driving port for slice-01 is the
existing `scripts/hooks/spine_ledger_gate.py` script. The `BypassCause` StrEnum
value object does NOT EXIST YET (DELIVER scope is to extract it). AT-2's
composition fixture imports `BypassCause` from the production module; when the
symbol is absent, the import surfaces as `ImportError` -> wrap-and-re-raise as
`AssertionError` so the RED classification is correct (Mandate 7 RED-not-BROKEN).
AT-1's parity outline runs against the CURRENT gate (cause vocabulary still
literal strings) and is expected to PASS today — its RED-edge fires only if
DELIVER's refactor drifts the JSON shape (negative regression guard).
AT-3 invokes the predecessor-feature suite via pytest as a subprocess; the
suite passes today and MUST keep passing post-refactor.

The whole module is marked skip at file-head per ADR-028 + friction #26 — the
DELIVER crafter unskips ONE scenario at a time during the inner TDD loop.
"""

from __future__ import annotations

import os

import pytest


_BYPASS_ENV = "NWAVE_SPINE_LEDGER_GATE_BYPASS"


@pytest.fixture(autouse=True)
def _isolate_bypass_env() -> object:
    """Restore NWAVE_SPINE_LEDGER_GATE_BYPASS around every test in this suite.

    The AT-1 env-bypass parametrize case sets the env var; without restoration
    it leaks into the dormant / block-refused / block-allowed cases of the
    SAME outline where the absence of the env var is part of the precondition.
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
