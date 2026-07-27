"""pytest-bdd binding for fix-wave-bypass-recovery-truthful slice-02 scenarios.

Driving surface (Mandate-13 driving-port-only, Layer 3 subprocess): the REAL
``des wave-clear`` subcommand via the production CLI dispatcher; observables are
the exit code + the floor file + the audit-log file. Step bodies delegate to the
composition root (``composition_slice_02_wave_clear.py``); no business logic in
step bodies (Mandate-12 criterion 3). The ``<state>`` / ``<outcome>`` tokens are
parsed once into the typed ``FloorState`` / ``ClearOutcome`` enums, so the step
templates range over the typed domain vocabulary (DSL emergence, not decorator
proliferation).

Active-RED scaffold (atdd_pure -- NOT @skip): RED until DELIVER registers the
``wave-clear`` row + ships ``src/des/cli/wave_clear.py`` +
``WaveActivationService.clear_floor()``. At HEAD the unregistered subcommand
yields ``invalid choice: 'wave-clear'`` (exit 2); the observable effect never
happens, so each Then fails with a semantic AssertionError, never a collection /
import error.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_02_wave_clear import WaveClearComposition
from .domain_types_wave_bypass_recovery import ClearOutcome, FloorState


scenarios("../slice-wave-bypass-recovery-02-wave-clear.feature")


@pytest.fixture
def clear() -> WaveClearComposition:
    return WaveClearComposition()


# --- Given -----------------------------------------------------------------


@given(parsers.parse("a wave floor armed in the {state} state for the clear"))
def given_floor_state(clear: WaveClearComposition, state: str, tmp_path: Path) -> None:
    clear.given_floor_state(tmp_path, FloorState[state])


@given("the maintainer omits the mandatory reason on the clear")
def given_clear_invoked_without_reason(clear: WaveClearComposition) -> None:
    clear.given_clear_invoked_without_reason()


# --- When ------------------------------------------------------------------


@when("the maintainer runs the sanctioned wave-clear command")
def when_operator_runs_wave_clear(clear: WaveClearComposition) -> None:
    clear.when_operator_runs_wave_clear()


# --- Then ------------------------------------------------------------------


@then(parsers.parse("the wave-clear command exits with the {outcome} outcome"))
def then_clear_exits(clear: WaveClearComposition, outcome: str) -> None:
    clear.then_clear_exits(ClearOutcome[outcome])


@then("the stale floor record is removed by the clear")
def then_floor_record_removed(clear: WaveClearComposition) -> None:
    clear.then_floor_record_removed()


@then("the usage error names the mandatory reason argument")
def then_usage_error_names_the_reason_argument(clear: WaveClearComposition) -> None:
    clear.then_usage_error_names_the_reason_argument()


@then("the stale floor record is left untouched by the refused clear")
def then_floor_record_untouched(clear: WaveClearComposition) -> None:
    clear.then_floor_record_untouched()


@then("the next markerless dispatch is no longer wave-bypass blocked")
def then_next_dispatch_no_longer_bypass_blocked(clear: WaveClearComposition) -> None:
    clear.then_next_dispatch_no_longer_bypass_blocked()


@then("the clear writes a wave-floor audit record")
def then_an_audit_record_was_written(clear: WaveClearComposition) -> None:
    clear.then_an_audit_record_was_written()


@then("the no-op message names the inspected project root")
def then_noop_message_names_project_root(clear: WaveClearComposition) -> None:
    clear.then_noop_message_names_project_root()


@then("the clear writes no third provenance value")
def then_clear_writes_no_third_provenance_value(clear: WaveClearComposition) -> None:
    clear.then_clear_writes_no_third_provenance_value()


@then("the INDETERMINATE diagnostic is written to stderr")
def then_indeterminate_diagnostic_on_stderr(clear: WaveClearComposition) -> None:
    clear.then_indeterminate_diagnostic_on_stderr()


@then("stdout carries no wave-clear outcome line")
def then_stdout_carries_no_outcome_line(clear: WaveClearComposition) -> None:
    clear.then_stdout_carries_no_outcome_line()
