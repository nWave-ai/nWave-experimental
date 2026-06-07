"""pytest-bdd binding for the dormant-seam gate walking skeleton (slice-01).

Driving port: the production ``des dormant-seam-gate`` composition-root CLI,
invoked as a subprocess black box (Mandate-13 driving-port-only, Layer 3
subprocess). Step bodies delegate to the composition root (``composition.py``);
no production module is imported-and-called at the step boundary, and no
business logic lives in a step body (Mandate-12: each body is a single
delegation).

The ``scenarios(...)`` call binds every scenario in the ``.feature`` file via
the RELATIVE path from this steps/ module -- the proven-collecting form used by
the sibling suites (oss-upstream-gate-pair-traceability /
oss-hook-side-phase-injection). This routes the scenario @tags through
pytest-bdd's tag-to-dynamic-mark pipeline, which the project's filterwarnings
makes --strict-markers-safe. Each step decorator's literal text is unique within
this feature directory (S1 step-text-uniqueness invariant; this is the only step
file in the directory).

RED scaffold: until DELIVER ships ``des.cli.dormant_seam_gate`` (+ the pure
detector + the changed-symbol port), the subprocess produces no JSON verdict, so
the Then-steps fail with a semantic ``AssertionError`` (no parseable verdict /
seam not named / non-zero exit) -- never a collection / import / setup error in
the test process (pre-DELIVER fail-for-right-reason gate).
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition import DormantSeamGateComposition


scenarios("../slice-01-dormant-seam-walking-skeleton.feature")


@pytest.fixture
def composition() -> DormantSeamGateComposition:
    return DormantSeamGateComposition()


# --- Given -------------------------------------------------------------------


@given(
    "a feature whose net-new delta adds an effectful public symbol that no "
    "production code calls"
)
def given_dormant_seam(composition: DormantSeamGateComposition) -> None:
    composition.given_dormant_net_new_effectful_symbol()


@given(
    "a feature whose net-new delta adds an effectful public symbol that "
    "production code calls"
)
def given_wired_seam(composition: DormantSeamGateComposition) -> None:
    composition.given_wired_net_new_effectful_symbol()


# --- When --------------------------------------------------------------------


@when("the developer runs the dormant-seam gate against that feature at GREEN-phase")
def when_runs_gate(composition: DormantSeamGateComposition) -> None:
    composition.when_developer_runs_the_gate()


# --- Then --------------------------------------------------------------------


@then("the gate names the dormant seam in its loud warning")
def then_names_dormant_seam(composition: DormantSeamGateComposition) -> None:
    composition.then_names_dormant_seam()


@then("the gate lets the wave proceed without blocking")
def then_lets_wave_proceed(composition: DormantSeamGateComposition) -> None:
    composition.then_lets_wave_proceed()


@then("the gate exits with code zero")
def then_exits_zero(composition: DormantSeamGateComposition) -> None:
    composition.then_exits_zero()


@then("the gate stays silent about the wired seam")
def then_silent_about_wired_seam(composition: DormantSeamGateComposition) -> None:
    composition.then_silent_about_wired_seam()


@then("the gate reports an indeterminate verdict that warns without refusing the wave")
def then_indeterminate_non_halting(composition: DormantSeamGateComposition) -> None:
    composition.then_indeterminate_warns_without_refusing()
