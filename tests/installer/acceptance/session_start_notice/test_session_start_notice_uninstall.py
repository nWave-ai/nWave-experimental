"""Executable oracle: uninstall removes the session-start injection entirely.

Authority: docs/product/architecture/brief.md#Uninstall Removes The Session-Start
Injection Entirely.

The observation itself lives in ``uninstall_notice_oracle.py`` beside this file,
which drives only published artefacts -- the real installer and uninstaller
processes and the hook command they publish into ``settings.json`` -- and
imports no production symbol. This module is the declared entry point: running
it EXECUTES the observation, so the exit status carries the verdict.
"""

from __future__ import annotations

import json
import sys

import pytest
from tests.installer.acceptance.session_start_notice.uninstall_notice_oracle import (
    EXPECTED_SEMANTIC_OBSERVATION,
    observe_uninstall_removes_session_start_injection,
)


def test_uninstall_removes_the_session_start_injection_entirely() -> None:
    """Uninstalling nWave from a project removes the session-start injection
    entirely, the way the retirement path already removes the two historical
    arrays -- observable by uninstalling and starting a session that carries no
    injected notice and no residual hook entry."""
    observed = observe_uninstall_removes_session_start_injection()

    assert observed["semantic"] == EXPECTED_SEMANTIC_OBSERVATION, (
        "WHAT: after a successful uninstall the session-start injection was not "
        "fully removed.\n"
        f"Observed: {observed['semantic']!r}\n"
        f"Expected: {EXPECTED_SEMANTIC_OBSERVATION!r}\n"
        f"Diagnostics: {observed['diagnostics']!r}\n"
        "WHY: uninstall must leave no installer-owned SessionStart entry behind. "
        "A surviving entry points at a deleted module, so every later session "
        "start runs a dangling installer-owned command that fails -- while the "
        "SessionStart array's other producers must be preserved byte-for-byte.\n"
        "HOW: strip installer-owned commands from EVERY event array under the "
        "same ownership selector the install path already uses, without adding a "
        "second ownership vocabulary and without touching the exact/digest pass "
        "that governs the historical shell payloads."
    )


if __name__ == "__main__":
    observation = observe_uninstall_removes_session_start_injection()
    print(json.dumps(observation, indent=2, sort_keys=True, default=str))
    sys.exit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
