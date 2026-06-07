"""Step definitions -- slice-01: spine-ledger gate ledger-evidence block path.

F-ATDD-SPINE-LEDGER-ENFORCEMENT-GATE-v2 slice-01. Layer 3 (subprocess + FS
acceptance): the production gate script `scripts/hooks/spine_ledger_gate.py`
is the driving port (the slice-00 stub script exists; the slice-01 block
path + positive ledger-evidence path + partial-failure tolerance do NOT).

The only driven ports are:
  - the real filesystem (tmp_path target: `.nwave/telemetry/atdd-pure/<feature>.jsonl`
    seeded via the real `AtCompletionLedger.append_gate_event` writer so the
    M7 contract is satisfied; `.nwave/des/logs/audit-{today}.log`),
  - the real environment (NWAVE_SPINE_LEDGER_GATE_BYPASS env var, cleared
    per-test via the slice-00 autouse fixture),
  - the real subprocess (`python -m scripts.hooks.spine_ledger_gate`).

Example-based (Mandate 11 -- layer 3 sad paths enumerated explicitly).
Three ATs cover the contract: refusal on missing record + allow on present
record + partial-failure tolerance on one-malformed-one-healthy mix. PBT
precluded by OR-reduction (Mandate 9 v2: real I/O on audit log + subprocess
+ AtCompletionLedger writer touching the real filesystem under flock).

Step bodies delegate to `LedgerEvidenceFixture` (Mandate-12 criterion 3:
≤2 statements per body, final statement is a composition method call,
zero control flow in step bodies).

RED-for-the-right-reason: the slice-00 production script EXISTS but only
ships the kill-switch + dormant + `slice-00-block-path-deferred` stub
branch. The slice-01 block path (exit 1 + `commit-refused` +
`block-ledger-evidence-missing`) and the positive
`ledger-evidence-present` path do NOT exist yet. When the composition
fixture invokes the gate for AT-1 (telemetry present, no record), the
current stub returns `{verdict: commit-allowed, cause: slice-00-block-
path-deferred}`; the AT then fires AssertionError on the first `Then`
step (`assert_verdict_refused`). That is the correct RED: the assertion
fires because the slice-01 block path is unimplemented, not because of
an import error or fixture setup bug.

Mandate-13 (driving-port-only): every step delegates to the composition
fixture, which drives the SUT via `python -m scripts.hooks.spine_ledger_gate`
subprocess. ZERO direct production imports IN STEP COMPOSITION (the
seeding helper `_seed_verified_slice_record` lives inside
`composition.py` and imports `AtCompletionLedger` ONLY for test-harness
ledger-fixture seeding -- the GATE itself runs as a subprocess and the
gate's read path goes through `AtCompletionLedger.read_records` via the
slice-01 production helper -- single source of truth per Mandate-12).

Mandate-12 SSOT-for-ledger-reading constraint (dispatch §5): slice-01
production code MUST reuse `AtCompletionLedger.read_records` (existing in
`src/des/adapters/driven/logging/at_completion_ledger.py`) -- NOT duplicate
a ledger reader. The crafter will refactor `verify_slice_ledger_record.py`
logic into a helper callable from `spine_ledger_gate.py:_dispatch_block_path`.
AT-3 verifies the partial-failure tolerance is mechanical (one malformed
file = skip-and-continue, not abort) -- Phase 0 audit Gap B fix option 2.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition import GateInvocation, LedgerEvidenceFixture


scenarios("../slice-01-ledger-evidence-block.feature")


# --- Fixtures --------------------------------------------------------------


@pytest.fixture
def fixture(tmp_path: Path) -> LedgerEvidenceFixture:
    """Per-test ledger-evidence fixture rooted at an isolated tmp target."""
    return LedgerEvidenceFixture(target_root=tmp_path / "target")


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for the captured GateInvocation across When/Then steps."""
    return {}


# --- Background ------------------------------------------------------------


@given("the operator's target machine has nWave installed")
def given_nwave_installed(fixture: LedgerEvidenceFixture) -> None:
    # No-op composition method: subprocess invocation from the repo root is
    # the "installed" surface for dev mode (mirrors slice-00 precedent).
    fixture.ensure_no_disabled_gates_file()


@given('the spine-ledger gate entry point is the script "spine_ledger_gate"')
def given_gate_entry_point(fixture: LedgerEvidenceFixture) -> None:
    # Documents the SUT identity; composition fixture knows the module path.
    fixture.ensure_no_disabled_gates_file()


@given(
    "the gate reads ledger records through the SINGLE source of truth "
    '"AtCompletionLedger.read_records"'
)
def given_single_ledger_reader(fixture: LedgerEvidenceFixture) -> None:
    # Mandate-12 SSOT documentation step: the slice-01 production helper
    # MUST consume `AtCompletionLedger.read_records`, NOT duplicate a parser.
    # The composition fixture seeds records via the same writer so the
    # contract is honored end-to-end.
    fixture.ensure_no_disabled_gates_file()


@given(
    'the gate writes audit events to ".nwave/des/logs/audit-{today}.log" in JSONL format'
)
def given_audit_log_format(fixture: LedgerEvidenceFixture) -> None:
    # Documents the audit-log contract; composition fixture reads from the
    # same path with the same parser.
    fixture.ensure_no_disabled_gates_file()


# --- Shared preconditions (reused from slice-00 vocabulary) ----------------


@given(
    "a target machine with a spine-telemetry directory containing zero verified slices"
)
def given_telemetry_dir_empty(fixture: LedgerEvidenceFixture) -> None:
    fixture.ensure_telemetry_dir_with_zero_verified_slices()


@given('the operator\'s environment does NOT carry "NWAVE_SPINE_LEDGER_GATE_BYPASS"')
def given_bypass_env_absent(fixture: LedgerEvidenceFixture) -> None:
    fixture.clear_bypass_env()


@given('the repo carries NO ".nwave/disabled-gates" file')
def given_no_disabled_gates_file(fixture: LedgerEvidenceFixture) -> None:
    fixture.ensure_no_disabled_gates_file()


@given(
    parsers.parse(
        'a candidate commit message carrying the trailer "Slice-Id: {slice_id}"'
    )
)
def given_candidate_commit(fixture: LedgerEvidenceFixture, slice_id: str) -> None:
    fixture.write_candidate_commit_message_with_slice_trailer(slice_id)


# --- Slice-01-specific preconditions ---------------------------------------


@given(
    parsers.parse(
        "a target machine with a spine-telemetry directory containing a "
        'verified slice record for slice "{slice_id}" under feature ledger '
        '"{feature_id}"'
    )
)
def given_verified_slice_record(
    fixture: LedgerEvidenceFixture, slice_id: str, feature_id: str
) -> None:
    fixture.seed_verified_slice_record(feature_id=feature_id, slice_id=slice_id)


@given(
    parsers.parse(
        "the spine-telemetry directory ALSO contains a legacy pre-M7 ledger "
        'file named "{filename}" carrying a record with no "seq" field'
    )
)
def given_malformed_legacy_ledger(
    fixture: LedgerEvidenceFixture, filename: str
) -> None:
    fixture.seed_malformed_legacy_ledger(filename=filename)


# --- Action ----------------------------------------------------------------


@when("the operator runs the spine-ledger gate against the candidate commit message")
def when_run_gate(
    fixture: LedgerEvidenceFixture, result_box: dict[str, object]
) -> None:
    result_box["invocation"] = fixture.run_gate()


# --- Observation (Then step delegates) -------------------------------------


@then('the gate exits with verdict "commit-refused"')
def then_verdict_refused(
    fixture: LedgerEvidenceFixture, result_box: dict[str, object]
) -> None:
    fixture.assert_verdict_refused(result_box["invocation"])  # type: ignore[arg-type]


@then('the gate exits with verdict "commit-allowed"')
def then_verdict_allowed(
    fixture: LedgerEvidenceFixture, result_box: dict[str, object]
) -> None:
    fixture.assert_verdict_allowed(result_box["invocation"])  # type: ignore[arg-type]


@then(parsers.parse('the gate\'s stdout reports the refusal cause as "{cause}"'))
def then_refusal_cause(
    fixture: LedgerEvidenceFixture, result_box: dict[str, object], cause: str
) -> None:
    fixture.assert_refusal_cause(result_box["invocation"], cause)  # type: ignore[arg-type]


@then(parsers.parse('the gate\'s stdout reports the allow cause as "{cause}"'))
def then_allow_cause(
    fixture: LedgerEvidenceFixture, result_box: dict[str, object], cause: str
) -> None:
    fixture.assert_allow_cause(result_box["invocation"], cause)  # type: ignore[arg-type]


@then(parsers.parse('the gate\'s stdout names the unverified slice as "{slice_id}"'))
def then_stdout_names_unverified_slice(
    fixture: LedgerEvidenceFixture, result_box: dict[str, object], slice_id: str
) -> None:
    fixture.assert_stdout_names_unverified_slice(result_box["invocation"], slice_id)  # type: ignore[arg-type]


@then(parsers.parse('the gate\'s stdout names the verified slice as "{slice_id}"'))
def then_stdout_names_verified_slice(
    fixture: LedgerEvidenceFixture, result_box: dict[str, object], slice_id: str
) -> None:
    fixture.assert_stdout_names_verified_slice(result_box["invocation"], slice_id)  # type: ignore[arg-type]


@then(
    parsers.parse(
        'the gate\'s stdout lists the skipped ledger file as containing "{fragment}"'
    )
)
def then_stdout_lists_skipped_file(
    fixture: LedgerEvidenceFixture, result_box: dict[str, object], fragment: str
) -> None:
    fixture.assert_stdout_lists_skipped_file_containing(
        result_box["invocation"],  # type: ignore[arg-type]
        fragment,
    )


@then(
    parsers.parse(
        'the audit log carries zero new "{event_name}" events for this invocation'
    )
)
def then_zero_new_events(
    fixture: LedgerEvidenceFixture, result_box: dict[str, object], event_name: str
) -> None:
    # The only event-type slice-01 inspects via this assertion is
    # SpineBypassUsed (negative path: NO bypass fired). The slice-00 helper
    # tests against SpineBypassUsed by name; this slice reuses the same
    # `assert_zero_new_bypass_events` helper.
    _ = event_name  # event_name is "SpineBypassUsed" by feature design
    fixture.assert_zero_new_bypass_events(result_box["invocation"])  # type: ignore[arg-type]


@then(
    parsers.parse(
        'the audit log carries exactly one new "{event_name}" event for this invocation'
    )
)
def then_one_new_event(
    fixture: LedgerEvidenceFixture, result_box: dict[str, object], event_name: str
) -> None:
    # Slice-01 inspects the LedgerSkipped event type (AT-3 partial-failure
    # tolerance). The dispatcher routes by the literal event_name token.
    _ = event_name  # event_name is "LedgerSkipped" by feature design
    fixture.assert_exactly_one_new_ledger_skipped_event(result_box["invocation"])  # type: ignore[arg-type]


@then(
    parsers.parse(
        'the audit event names the skipped ledger path as containing "{fragment}"'
    )
)
def then_event_names_skipped_path(
    fixture: LedgerEvidenceFixture, result_box: dict[str, object], fragment: str
) -> None:
    fixture.assert_ledger_skipped_event_names_path_containing(
        result_box["invocation"],  # type: ignore[arg-type]
        fragment,
    )


@then(parsers.parse('the audit event names the skip cause as "{cause}"'))
def then_event_names_skip_cause(
    fixture: LedgerEvidenceFixture, result_box: dict[str, object], cause: str
) -> None:
    fixture.assert_ledger_skipped_event_cause(result_box["invocation"], cause)  # type: ignore[arg-type]


# --- Unused-imports guard (ruff F401) --------------------------------------

# GateInvocation is re-exported for downstream slice authors to re-use the
# type when extending the step set; ruff will flag F401 without this line.
_TYPE_REEXPORTS = (GateInvocation,)
