"""Step definitions -- slice-03: spine-ledger SubagentStop soft-escalation detector.

F-ATDD-SPINE-LEDGER-ENFORCEMENT-GATE-v2 slice-03. Layer 3 (subprocess + FS
acceptance + Claude Code SubagentStop hook protocol simulation): the
production hook script `scripts/hooks/spine_ledger_subagent_stop_detector.py`
is the driving port.

The only driven ports are:
  - the real filesystem (tmp_path target: `.nwave/telemetry/atdd-pure/`,
    `.nwave/des/logs/audit-{today}.jsonl`, synthetic
    `agent-transcript.jsonl`),
  - the real environment (NWAVE_SPINE_LEDGER_GATE_BYPASS env var, cleared
    per-test via the slice-00 autouse fixture; plus slice-02 introduces
    NWAVE_SPINE_LEDGER_GATE_TARGET_ROOT + NWAVE_SPINE_LEDGER_GATE_LEDGER_ROOT
    for test-harness parameter passing to the hook subprocess),
  - the real subprocess
    (`python -m scripts.hooks.spine_ledger_subagent_stop_detector`,
    invoked with Claude Code SubagentStop hook-event JSON on stdin),
  - the real ledger writer (`AtCompletionLedger.append_gate_event`,
    used by AT-3 to seed a CarpaccioGateCleared event via the same SSOT
    writer the production hook reads from -- Mandate-12).

Example-based (Mandate 11 -- layer 3 sad paths enumerated explicitly).
Three ATs cover the slice-03 contract: walking-skeleton bypass-detected
emission + read-only fast-path skip + spine-cleared honour. PBT precluded
by OR-reduction (Mandate 9 v2: real I/O on subprocess + audit log +
AtCompletionLedger writer touching real flock).

Step bodies delegate to `SubagentStopDetectorFixture` (Mandate-12
criterion 3: ≤2 statements per body, final statement is a composition
method call, zero control flow in step bodies).

RED-for-the-right-reason: the slice-03 production hook script
`scripts/hooks/spine_ledger_subagent_stop_detector.py` does NOT EXIST
YET (the crafter lands it in DELIVER). When the composition fixture
invokes it as a subprocess via `python -m`, the interpreter returns a
non-zero exit with stderr naming the missing module; the AT then fires
AssertionError on the first `Then` step
(`assert_exactly_one_new_bypass_detected_event` or
`assert_zero_new_bypass_detected_events`). That is the correct RED: the
assertion fires because the slice-03 hook entry point is unimplemented,
not because of an import error or fixture setup bug.

Mandate-13 (driving-port-only): every step delegates to the composition
fixture, which drives the SUT via
`python -m scripts.hooks.spine_ledger_subagent_stop_detector` subprocess
+ JSON stdin. ZERO direct production imports in step composition. The
slice-01 function-scope `AtCompletionLedger` import inside
`composition.py:_seed_carpaccio_gate_cleared_record` is the writer-side
test-harness seeding helper (same classification as slice-01's
`_seed_verified_slice_record`); slice-03 introduces ZERO additional
production imports in step composition.

Skip marker: per ADR-028 + friction #26 lesson (slice-02 missed this and
was orchestrator-patched), the whole module is marked `pytest.mark.skip`
AT FILE HEAD until the crafter lands the production hook script. The
crafter unskips on A_GREEN_ATS. This is the RED scaffold contract: the
ATs exist, classify as RED-for-the-right-reason in reviewer logs, but
do NOT execute against the missing production module on every CI run.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition import SubagentStopDetectorFixture, SubagentStopInvocation


scenarios("../slice-03-subagent-stop-detector.feature")


# --- Fixtures --------------------------------------------------------------


@pytest.fixture
def fixture(tmp_path: Path) -> SubagentStopDetectorFixture:
    """Per-test SubagentStop detector fixture rooted at an isolated tmp target."""
    return SubagentStopDetectorFixture(target_root=tmp_path / "target")


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for the captured SubagentStopInvocation across When/Then steps."""
    return {}


# --- Background ------------------------------------------------------------


@given(
    "the operator is inside a Claude Code session with the spine-ledger "
    "SubagentStop hook installed"
)
def given_subagent_stop_hook_installed(fixture: SubagentStopDetectorFixture) -> None:
    # No-op composition method: subprocess invocation from the repo root
    # models the "installed" surface for dev mode (the installer plugin
    # ships the hook entry in `scripts/install/plugins/des_plugin.py` per
    # slice-04, NOT slice-03). The step exists so the Gherkin reads as a
    # business precondition (Pillar 1).
    fixture.ensure_no_disabled_gates_file()


@given(
    "the spine-ledger SubagentStop hook entry point is the script "
    '"subagent_stop_spine_detector"'
)
def given_subagent_stop_hook_entry_point(
    fixture: SubagentStopDetectorFixture,
) -> None:
    # Documents the SUT identity. The composition fixture knows the module
    # path; no business logic in the step body.
    fixture.ensure_no_disabled_gates_file()


@given(
    "the hook speaks the Claude Code SubagentStop protocol — JSON stdin, "
    "audit-log side-effect, exit code as soft signal"
)
def given_subagent_stop_hook_protocol(
    fixture: SubagentStopDetectorFixture,
) -> None:
    # Documents the protocol contract: stdin = event JSON, audit log = the
    # universe-bound observable (Mandate 8), exit 0 always (slice-03 is
    # soft-escalation, NEVER blocks the sub-agent return).
    fixture.ensure_no_disabled_gates_file()


@given(
    'the hook writes audit events to ".nwave/des/logs/audit-{today}.jsonl" '
    "in JSONL format"
)
def given_audit_log_format(fixture: SubagentStopDetectorFixture) -> None:
    # Documents the audit-log contract; composition fixture reads from the
    # same path with the same parser (inherited from slice-00 KillSwitchFixture).
    fixture.ensure_no_disabled_gates_file()


# --- Shared preconditions (reused from slice-00/01/02 vocabulary) ----------


@given(
    "a target machine with a spine-telemetry directory containing zero verified slices"
)
def given_telemetry_dir_empty(fixture: SubagentStopDetectorFixture) -> None:
    fixture.ensure_telemetry_dir_with_zero_verified_slices()


@given('the operator\'s environment does NOT carry "NWAVE_SPINE_LEDGER_GATE_BYPASS"')
def given_bypass_env_absent(fixture: SubagentStopDetectorFixture) -> None:
    fixture.clear_bypass_env()


# --- Slice-03-specific preconditions ---------------------------------------


@given(
    'the current Claude Code session has NO preceding "CarpaccioGateCleared" '
    "event in the spine-telemetry directory"
)
def given_no_preceding_carpaccio_cleared_event(
    fixture: SubagentStopDetectorFixture,
) -> None:
    # The telemetry dir is empty (slice-00 precondition above already ran);
    # this step documents the cross-event-class invariant: no SliceCommitVerified
    # AND no CarpaccioGateCleared exists for any slice in the current session.
    # The composition fixture's `ensure_telemetry_dir_with_zero_verified_slices`
    # makes the dir empty (no records of any event type).
    fixture.ensure_telemetry_dir_with_zero_verified_slices()


@given(
    parsers.parse(
        "a target machine with a spine-telemetry directory containing one "
        'verified slice under feature "{feature_id}" slice "{slice_id}"'
    )
)
def given_telemetry_dir_with_verified_slice(
    fixture: SubagentStopDetectorFixture, feature_id: str, slice_id: str
) -> None:
    fixture.seed_verified_slice_record(feature_id, slice_id)


@given(
    parsers.parse(
        'the current Claude Code session has a preceding "CarpaccioGateCleared" '
        'event for slice "{slice_id}" recorded in the spine-telemetry directory'
    )
)
def given_preceding_carpaccio_cleared_event(
    fixture: SubagentStopDetectorFixture, slice_id: str
) -> None:
    fixture.seed_carpaccio_gate_cleared_event(
        "atdd-spine-ledger-enforcement-gate-v2", slice_id
    )


@given(
    parsers.parse(
        "an Agent sub-agent has returned with a transcript containing an "
        'Edit tool use on "{file_path}"'
    )
)
def given_agent_transcript_with_edit(
    fixture: SubagentStopDetectorFixture, file_path: str
) -> None:
    fixture.write_agent_transcript_with_edit_on_src_des(file_path)


@given(
    "an Agent sub-agent has returned with a transcript containing ONLY "
    "Read and Grep and Glob tool uses"
)
def given_agent_transcript_with_only_read_grep_glob(
    fixture: SubagentStopDetectorFixture,
) -> None:
    fixture.write_agent_transcript_with_only_read_grep_glob()


# --- Action ----------------------------------------------------------------


@when("the Claude Code session emits the SubagentStop event for the returning Agent")
def when_session_emits_subagent_stop(
    fixture: SubagentStopDetectorFixture,
) -> None:
    fixture.prepare_subagent_stop_event_for_agent_return()


@when("the SubagentStop hook receives the Agent return event")
def when_hook_receives_subagent_stop_event(
    fixture: SubagentStopDetectorFixture, result_box: dict[str, object]
) -> None:
    result_box["invocation"] = fixture.invoke_subagent_stop_hook()


# --- Observation (Then step delegates) -------------------------------------


@then(
    parsers.parse(
        'the audit log carries exactly one new "{event_name}" event for this '
        "Agent return"
    )
)
def then_exactly_one_new_event(
    fixture: SubagentStopDetectorFixture,
    result_box: dict[str, object],
    event_name: str,
) -> None:
    _ = event_name  # event_name is "SpineBypassDetected" by feature design
    fixture.assert_exactly_one_new_bypass_detected_event(
        result_box["invocation"]  # type: ignore[arg-type]
    )


@then(
    parsers.parse(
        'the audit log carries zero new "{event_name}" events for this Agent return'
    )
)
def then_zero_new_events(
    fixture: SubagentStopDetectorFixture,
    result_box: dict[str, object],
    event_name: str,
) -> None:
    _ = event_name  # event_name is "SpineBypassDetected" by feature design
    fixture.assert_zero_new_bypass_detected_events(
        result_box["invocation"]  # type: ignore[arg-type]
    )


@then(parsers.parse('the new audit event names the cause as "{cause}"'))
def then_new_event_names_cause(
    fixture: SubagentStopDetectorFixture,
    result_box: dict[str, object],
    cause: str,
) -> None:
    fixture.assert_bypass_detected_event_cause(
        result_box["invocation"],  # type: ignore[arg-type]
        cause,
    )


@then(
    parsers.parse(
        "the new audit event names at least one transcript-evidence entry "
        'containing "{fragment}"'
    )
)
def then_new_event_names_evidence(
    fixture: SubagentStopDetectorFixture,
    result_box: dict[str, object],
    fragment: str,
) -> None:
    fixture.assert_bypass_detected_event_names_evidence_containing(
        result_box["invocation"],  # type: ignore[arg-type]
        fragment,
    )


@then("the new audit event carries the transcript path of the returning Agent")
def then_new_event_carries_transcript_path(
    fixture: SubagentStopDetectorFixture, result_box: dict[str, object]
) -> None:
    fixture.assert_bypass_detected_event_carries_transcript_path(
        result_box["invocation"]  # type: ignore[arg-type]
    )


@then("the hook returns a soft-pass decision to Claude Code")
def then_soft_pass_decision_returned(
    fixture: SubagentStopDetectorFixture, result_box: dict[str, object]
) -> None:
    fixture.assert_soft_pass_decision_returned(
        result_box["invocation"]  # type: ignore[arg-type]
    )


@then("the target machine filesystem is unchanged outside transient hook logging")
def then_filesystem_unchanged_outside_hook_logs(
    fixture: SubagentStopDetectorFixture, result_box: dict[str, object]
) -> None:
    fixture.assert_filesystem_unchanged_outside_audit_log(
        result_box["invocation"]  # type: ignore[arg-type]
    )


# --- Unused-imports guard (ruff F401) --------------------------------------

# SubagentStopInvocation is re-exported for downstream slice authors to
# re-use the type when extending the step set; ruff will flag F401 without
# this line.
_TYPE_REEXPORTS = (SubagentStopInvocation,)
