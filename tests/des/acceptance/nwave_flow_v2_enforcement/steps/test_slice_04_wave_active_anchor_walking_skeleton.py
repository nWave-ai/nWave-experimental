"""pytest-bdd binding for the wave-active anchor walking skeleton (slice-04).

Driving port: the REAL prompt-submission hook process, invoked as a subprocess
(Mandate-13 driving-port-only, Layer 4 wiring_e2e). Step bodies delegate to the
composition root (``composition.py``); no production module is imported-and-
called at the step boundary, and no business logic lives in a step body
(Mandate-12: each body is a single delegation).

``scenarios(...)`` binds via the RELATIVE path from this steps/ module (the
proven-collecting form). Each step decorator's literal text is unique within this
feature directory (S1 step-text-uniqueness invariant; the literals here are
disjoint from the read+scope step file's literals).

Active-RED scaffold (ADR-025 + ADR-028, atdd_pure -- NOT @skip): until DELIVER
ships the submission hook wiring, the subprocess writes no floor file, so the
Then-steps read the absent floor through the composition and fail with a semantic
``AssertionError`` (no record armed / wrong provenance) -- never a collection /
import / setup error (pre-DELIVER fail-for-right-reason gate).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition import WaveActiveAnchorComposition
from .domain_types import Wave


scenarios("../slice-04-wave-active-anchor-walking-skeleton.feature")


@pytest.fixture
def composition() -> WaveActiveAnchorComposition:
    return WaveActiveAnchorComposition()


# --- Given -------------------------------------------------------------------


@given("a clean project where no wave is active")
def given_clean_project(
    composition: WaveActiveAnchorComposition, tmp_path: Path
) -> None:
    composition.given_clean_project_no_wave_active(tmp_path)


# --- When --------------------------------------------------------------------


@when("the user submits the prompt that starts the discuss wave")
def when_user_submits_discuss_command(
    composition: WaveActiveAnchorComposition,
) -> None:
    composition.when_user_submits_wave_command(Wave.DISCUSS)


# --- Then --------------------------------------------------------------------


@then("the discuss wave is recorded as active in the project")
def then_discuss_wave_recorded(composition: WaveActiveAnchorComposition) -> None:
    composition.then_wave_recorded_active(Wave.DISCUSS)


@then("the wave was armed deterministically from the command, not self-reported")
def then_armed_from_command(composition: WaveActiveAnchorComposition) -> None:
    composition.then_armed_deterministically_from_command()


@then("no other wave is recorded as active")
def then_no_other_wave(composition: WaveActiveAnchorComposition) -> None:
    composition.then_no_other_wave_active(Wave.DISCUSS)
