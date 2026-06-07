"""Step definitions -- slice-00: spine-ledger gate kill-switch.

F-ATDD-SPINE-LEDGER-ENFORCEMENT-GATE-v2 slice-00. Layer 3 (subprocess + FS
acceptance): the production gate script `scripts/hooks/spine_ledger_gate.py`
is the driving port; the only driven ports are the real filesystem
(tmp_path target), the real environment (NWAVE_SPINE_LEDGER_GATE_BYPASS),
and the audit log writer (real JSONL under `.nwave/des/logs/`).

Example-based (Mandate 11 -- layer 3 sad paths enumerated explicitly).
Three ATs cover the contract: env-var bypass + file bypass + dormant-mode
absent telemetry. PBT precluded by OR-reduction (Mandate 9 v2: real I/O on
audit log + subprocess).

Step bodies delegate to `KillSwitchFixture` (Mandate-12 criterion 3:
≤2 statements per body, final statement is a composition method call,
zero control flow in step bodies).

RED-for-the-right-reason: the production driving port script
`scripts/hooks/spine_ledger_gate.py` does NOT exist yet. The composition
fixture invokes it as a real subprocess; absent script -> non-zero exit ->
`assert_verdict_allowed` raises AssertionError on the first `Then` step.
That is the correct RED: assertion fires because the implementation is
missing, not because of an import error or fixture setup bug.

Mandate-13 (driving-port-only): every step delegates to the composition
fixture, which drives the SUT via `python -m scripts.hooks.spine_ledger_gate`
subprocess. ZERO direct production imports. ZERO function-boundary
invocation of production modules.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition import GateInvocation, KillSwitchFixture


scenarios("../slice-00-kill-switch.feature")


# --- Fixtures --------------------------------------------------------------


@pytest.fixture
def fixture(tmp_path: Path) -> KillSwitchFixture:
    """Per-test kill-switch fixture rooted at an isolated tmp target."""
    return KillSwitchFixture(target_root=tmp_path / "target")


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for the captured GateInvocation across When/Then steps."""
    return {}


# --- Background ------------------------------------------------------------


@given("the operator's target machine has nWave installed")
def given_nwave_installed(fixture: KillSwitchFixture) -> None:
    # No-op composition method: the production gate script is invoked as a
    # subprocess from the repo root (the "installed" surface for dev mode).
    # The step exists so the Gherkin reads as a business precondition (Pillar 1).
    fixture.ensure_no_disabled_gates_file()


@given('the spine-ledger gate entry point is the script "spine_ledger_gate"')
def given_gate_entry_point(fixture: KillSwitchFixture) -> None:
    # Documents the SUT identity. Composition fixture knows the module path;
    # no business logic in the step body.
    fixture.ensure_no_disabled_gates_file()


@given(
    'the gate writes audit events to ".nwave/des/logs/audit-{today}.log" in JSONL format'
)
def given_audit_log_format(fixture: KillSwitchFixture) -> None:
    # Documents the audit-log contract. The composition fixture reads from
    # the same path with the same parser.
    fixture.ensure_no_disabled_gates_file()


# --- Shared preconditions --------------------------------------------------


@given(
    "a target machine with a spine-telemetry directory containing zero verified slices"
)
def given_telemetry_dir_empty(fixture: KillSwitchFixture) -> None:
    fixture.ensure_telemetry_dir_with_zero_verified_slices()


@given(
    "a target machine that has NOT adopted the spine "
    '(no ".nwave/telemetry/atdd-pure/" directory exists)'
)
def given_no_telemetry_dir(fixture: KillSwitchFixture) -> None:
    fixture.ensure_no_telemetry_dir()


@given('the operator\'s environment carries "NWAVE_SPINE_LEDGER_GATE_BYPASS=1"')
def given_bypass_env_set(fixture: KillSwitchFixture) -> None:
    fixture.set_bypass_env("1")


@given('the operator\'s environment does NOT carry "NWAVE_SPINE_LEDGER_GATE_BYPASS"')
def given_bypass_env_absent(fixture: KillSwitchFixture) -> None:
    fixture.clear_bypass_env()


@given(
    'the repo carries a ".nwave/disabled-gates" file listing '
    '"spine-ledger-gate" on its own line'
)
def given_disabled_gates_file(fixture: KillSwitchFixture) -> None:
    fixture.write_disabled_gates_file_naming_spine_gate()


@given('the repo carries NO ".nwave/disabled-gates" file')
def given_no_disabled_gates_file(fixture: KillSwitchFixture) -> None:
    fixture.ensure_no_disabled_gates_file()


@given(
    parsers.parse(
        'a candidate commit message carrying the trailer "Slice-Id: {slice_id}"'
    )
)
def given_candidate_commit(fixture: KillSwitchFixture, slice_id: str) -> None:
    fixture.write_candidate_commit_message_with_slice_trailer(slice_id)


# --- Action ----------------------------------------------------------------


@when("the operator runs the spine-ledger gate against the candidate commit message")
def when_run_gate(fixture: KillSwitchFixture, result_box: dict[str, object]) -> None:
    result_box["invocation"] = fixture.run_gate()


# --- Observation -----------------------------------------------------------


@then('the gate exits with verdict "commit-allowed"')
def then_verdict_allowed(
    fixture: KillSwitchFixture, result_box: dict[str, object]
) -> None:
    fixture.assert_verdict_allowed(result_box["invocation"])  # type: ignore[arg-type]


@then(parsers.parse('the gate\'s stdout reports the bypass cause as "{cause}"'))
def then_bypass_cause(
    fixture: KillSwitchFixture, result_box: dict[str, object], cause: str
) -> None:
    fixture.assert_bypass_cause(result_box["invocation"], cause)  # type: ignore[arg-type]


@then(parsers.parse('the gate\'s stdout reports the dormant-mode cause as "{cause}"'))
def then_dormant_cause(
    fixture: KillSwitchFixture, result_box: dict[str, object], cause: str
) -> None:
    fixture.assert_bypass_cause(result_box["invocation"], cause)  # type: ignore[arg-type]


@then(
    parsers.parse(
        'the audit log carries exactly one new "{event_name}" event for this invocation'
    )
)
def then_one_new_event(
    fixture: KillSwitchFixture, result_box: dict[str, object], event_name: str
) -> None:
    _ = event_name  # event_name is "SpineBypassUsed" by feature design (single event class)
    fixture.assert_exactly_one_new_bypass_event(result_box["invocation"])  # type: ignore[arg-type]


@then(
    parsers.parse(
        'the audit log carries zero new "{event_name}" events for this invocation'
    )
)
def then_zero_new_events(
    fixture: KillSwitchFixture, result_box: dict[str, object], event_name: str
) -> None:
    _ = event_name
    fixture.assert_zero_new_bypass_events(result_box["invocation"])  # type: ignore[arg-type]


@then(parsers.parse('the audit event names the bypass source as "{source}"'))
def then_bypass_source(
    fixture: KillSwitchFixture, result_box: dict[str, object], source: str
) -> None:
    fixture.assert_bypass_event_source(result_box["invocation"], source)  # type: ignore[arg-type]


@then(parsers.parse('the audit event names the candidate slice as "{slice_id}"'))
def then_event_names_slice(
    fixture: KillSwitchFixture, result_box: dict[str, object], slice_id: str
) -> None:
    fixture.assert_bypass_event_names_slice(result_box["invocation"], slice_id)  # type: ignore[arg-type]


@then("the target machine filesystem is unchanged outside the audit log")
def then_filesystem_unchanged(fixture: KillSwitchFixture) -> None:
    fixture.assert_filesystem_unchanged_outside_audit_log()


# --- Unused-imports guard (ruff F401) --------------------------------------

# GateInvocation is imported for downstream slice authors to re-use the
# type when extending the step set; ruff will flag F401 without this line.
_TYPE_REEXPORTS = (GateInvocation,)
