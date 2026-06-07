"""pytest-bdd configuration for the copilot-cli-integration AT set.

Slice-01 (install-time contract): a real `install_nwave.py` / `uninstall_nwave.py`
subprocess wires (and later removes) the nWave DES hook config in the Copilot
runtime's hooks directory. The driving port is the real installer/uninstaller CLI
invoked as a Python subprocess against a tmp tree; the only driven ports are the
real filesystem (tmp COPILOT_HOME + tmp Claude config dir) and the COPILOT_HOME /
HOME / COPILOT_CLI environment variables.

The conftest is placed at the feature root (sibling of the .feature file) rather
than under steps/ -- this mirrors the codex-empirical-e2e-support and
fix-hmac-bootstrap-installer precedents and avoids a pytest plugin-name collision
with sibling features that also carry a steps/conftest.py.

Tmp-isolation (dispatch invariant 7): the real `~/.copilot/` is NEVER touched.
`CopilotInstallFixture` runs every subprocess with a fake HOME and a tmp
COPILOT_HOME; the autouse fixture below additionally restores the inherited
COPILOT_HOME / COPILOT_CLI env around each test so the var the fixture sets at
subprocess-launch time cannot leak into sibling suites.

RED-for-the-right-reason: there is no production scaffold authored by DISTILL --
the `copilot_des_plugin.py` and `TargetPlatform.COPILOT_CLI` enum are DELIVER
scope. The acceptance gap is the install-time seam (installer subprocess →
`<COPILOT_HOME>/hooks/nwave-des.json` in the FS-1 double-nested shape →
operator-observable surface). Slice-01 ATs fail with AssertionError because the
composition fixture runs the real installer AND asserts the install-contract
postcondition (the file-in-dir hook surface that fires on Copilot v1.0.54) -- the
seam either holds or it doesn't.
"""

from __future__ import annotations

import os

import pytest


_COPILOT_ENV_VARS = ("COPILOT_HOME", "COPILOT_CLI")


@pytest.fixture(autouse=True)
def _isolate_copilot_env():
    """Restore COPILOT_HOME / COPILOT_CLI around every test in this suite.

    `CopilotInstallFixture._sandboxed_env` sets these for the installer
    subprocess; this autouse fixture saves and restores the process-level values
    so they cannot leak into subsequent tests (mirrors the cross-suite-pollution
    guard added for fix-hmac-bootstrap-installer's signing-key env on 2026-05-24).
    """
    sentinel = object()
    saved = {var: os.environ.get(var, sentinel) for var in _COPILOT_ENV_VARS}
    try:
        yield
    finally:
        for var, value in saved.items():
            if value is sentinel:
                os.environ.pop(var, None)
            else:
                os.environ[var] = value  # type: ignore[arg-type]
