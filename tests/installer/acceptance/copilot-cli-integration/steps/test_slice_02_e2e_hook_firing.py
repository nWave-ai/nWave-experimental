"""Step definitions -- slice-02: Copilot CLI e2e hook-firing proof.

copilot-cli-integration slice-02. Layer 4+ (real-binary e2e): the driving port
is the REAL ``copilot`` binary invoked as a subprocess against a local mock
OpenAI SSE server (BYOK offline mode).

Example-only (Mandate 11 -- layer 4+; NO PBT machinery per Mandate 9).
Traditional assertions (Mandate 8 universe guard is layers 1-3 only). Two ATs,
each observing a DIFFERENT side-effect (revised iter-2 per reviewer Option A):
  - walking-skeleton (AT-1): production install → real session → the installed
    PRODUCTION adapter command fires → it writes a DES audit-log entry
    (HOOK_INVOKED / HOOK_COMPLETED). AT-1 observes that PRODUCTION side-effect —
    NOT the probe marker — so a GREEN can only come from the real production
    command firing (false-GREEN / Pista-2 trap avoided at its root). RED against
    slice-01: the production plugin wires only the non-firing preToolUse event
    (CRUX-1) in the un-wrapped schema v1.0.54 rejects (CRUX-2), so the command is
    never fired → no audit entry. slice-02 DELIVER must add sessionStart + the
    top-level ``hooks`` wrapper.
  - harness-soundness (AT-2): a hand-wired sessionStart marker hook fires
    reliably in the real binary — proves the mock-server + real-binary + firing
    harness is sound, so a RED on AT-1 is unambiguously a production gap, not a
    harness bug. The probe marker is legitimate for AT-2 (harness detection).

Step bodies delegate to ``CopilotE2EFixture`` (Mandate-12 criterion 3: <=2
statements per body, final statement is a composition method call, zero control
flow).

----------------------------------------------------------------------------
Two file-head guards (both required):
----------------------------------------------------------------------------
1. ADR-028 + friction #26 skip-marker: ``pytestmark`` includes
   ``pytest.mark.skip(...)`` so the whole slice stays RED-but-skipped until the
   DELIVER crafter unskips one scenario at a time in Phase A_GREEN_ATS.
2. skipif(copilot binary absent): the e2e SKIPS gracefully (never fails) on a
   runner / customer machine without the ``copilot`` binary. Absence != failure.

Tier note: this module lives under ``tests/installer/acceptance/`` (extending the
slice-01 feature dir per the dispatch brief), so conftest auto-marks it
``acceptance``. The explicit ``pytest.mark.e2e`` + ``pytest.mark.e2e_smoke`` here
ADD the e2e markers (add_marker is additive). Selection via ``-m e2e_smoke``
picks it up for the master/CI e2e tier; the heavy live-binary test stays off the
per-commit fast tier (which selects ``-m unit`` / excludes e2e). The Gherkin tags
``@e2e @e2e_smoke`` mirror the markers for tag-based selection.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .e2e_composition import (
    CopilotE2EFixture,
    CopilotFiringObservation,
    copilot_binary_path,
)


# Guard 1 (ADR-028 + friction #26): whole-slice skip until DELIVER unskips
# per-scenario. Guard 2: skip gracefully where the real copilot binary is absent.
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.e2e_smoke,
    pytest.mark.skip(
        reason="slice-02 pending: DELIVER unskips per scenario in Phase A_GREEN_ATS"
    ),
    pytest.mark.skipif(
        copilot_binary_path() is None,
        reason="copilot binary not present — e2e firing proof requires the real "
        "@github/copilot CLI; absence is a graceful skip, not a failure",
    ),
]


scenarios("../slice-02-e2e-hook-firing.feature")


# --- Fixtures --------------------------------------------------------------


@pytest.fixture
def fixture(tmp_path: Path) -> CopilotE2EFixture:
    """Live-binary e2e fixture rooted at an isolated tmp tree (fake HOME)."""
    return CopilotE2EFixture(tmp_root=tmp_path)


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for the captured firing observation across steps."""
    return {}


# --- Given -----------------------------------------------------------------


@given("an operator whose Copilot runtime is present")
def given_copilot_runtime_present(fixture: CopilotE2EFixture) -> None:
    fixture.stage_copilot_runtime()


@given("the operator has installed nWave for their Copilot runtime")
def given_installed_via_production(fixture: CopilotE2EFixture) -> None:
    fixture.install_via_production_plugin()


@given("an nWave hook is wired to write a marker when a Copilot session starts")
def given_probe_session_start_hook(fixture: CopilotE2EFixture) -> None:
    fixture.stage_probe_session_start_hook()


# --- When ------------------------------------------------------------------


@when("the operator runs a Copilot session")
def when_run_copilot_session(
    fixture: CopilotE2EFixture, result_box: dict[str, object]
) -> None:
    result_box["after"] = fixture.run_real_copilot_session()


# --- Then (walking-skeleton: production install fires) ----------------------


@then("the installed nWave hook fires during the Copilot session")
def then_installed_hook_fires(
    fixture: CopilotE2EFixture, result_box: dict[str, object]
) -> None:
    fixture.assert_production_hook_fired(_obs(result_box))


@then("the production install registered a hook on an event that actually fires")
def then_production_registers_firing_event(
    fixture: CopilotE2EFixture, result_box: dict[str, object]
) -> None:
    fixture.assert_production_hook_registers_firing_event(_obs(result_box))


# --- Then (harness-soundness: probe hook fires) ----------------------------


@then("the marker proves the hook fired during the Copilot session")
def then_marker_proves_firing(
    fixture: CopilotE2EFixture, result_box: dict[str, object]
) -> None:
    fixture.assert_probe_hook_fired(_obs(result_box))


@then("the marker carries the content the hook was wired to write")
def then_marker_content(
    fixture: CopilotE2EFixture, result_box: dict[str, object]
) -> None:
    fixture.assert_marker_content(_obs(result_box))


# --- internal: typed accessor for the captured surface ---------------------


def _obs(result_box: dict[str, object]) -> CopilotFiringObservation:
    """Return the captured observation; a helper so step bodies stay <=2 stmts."""
    return result_box["after"]  # type: ignore[return-value]
