"""Composition root for slice-00 (kill-switch) of the spine-ledger gate.

Wires the PRODUCTION spine-ledger gate script as a real Python subprocess
(Layer 3 driving port per Mandate-13) against a tmp_path target tree. The
only driven ports are:

  - the real filesystem (tmp_path target carries `.nwave/telemetry/atdd-pure/`,
    `.nwave/disabled-gates`, `.nwave/des/logs/audit-{today}.log`),
  - the real environment (NWAVE_SPINE_LEDGER_GATE_BYPASS env var),
  - the real subprocess (`python -m scripts.hooks.spine_ledger_gate`).

Business logic -- subprocess construction, audit-log discovery + parsing,
telemetry-dir creation, .disabled-gates authorship, commit-msg synthesis --
lives here as the single source of truth; step bodies delegate to
`KillSwitchFixture` methods and never inline logic (Mandate-12 criterion 3,
≤2 statements per step body).

RED-for-the-right-reason: the target script
`scripts/hooks/spine_ledger_gate.py` does NOT EXIST YET (it lands in a later
slice per the feature-delta `Wave: DISCUSS / [REF] Slice Plan` ordering;
slice-00 authors ATs + composition only). When `run_gate(...)` invokes the
absent script, subprocess returns a non-zero exit with a stderr naming the
missing module; the fixture surfaces this as `AssertionError` on the first
`Then` step that calls `assert_verdict_allowed`. That is the correct RED:
the assertion fires because the implementation is missing.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from nwave_ai.cli import _handle_install, _handle_uninstall
from tests.common.in_process_cli import run_cli_in_process, run_hook_in_process

from scripts.hooks import (
    spine_ledger_gate,
    spine_ledger_pre_commit_hook,
    spine_ledger_subagent_stop_detector,
)


# Repo root: tests/installer/acceptance/<feature>/steps/composition.py -> up five levels.
_REPO_ROOT = Path(__file__).resolve().parents[5]
_GATE_MODULE = "scripts.hooks.spine_ledger_gate"
_BYPASS_ENV = "NWAVE_SPINE_LEDGER_GATE_BYPASS"
_DISABLED_GATES_RELPATH = Path(".nwave") / "disabled-gates"
_TELEMETRY_RELPATH = Path(".nwave") / "telemetry" / "atdd-pure"
_AUDIT_LOG_DIR_RELPATH = Path(".nwave") / "des" / "logs"
_GATE_NAME = "spine-ledger-gate"
_BYPASS_EVENT = "SpineBypassUsed"


@dataclass(frozen=True)
class GateInvocation:
    """One captured invocation of the spine-ledger gate subprocess."""

    exit_code: int
    stdout: str
    stderr: str
    audit_events_before: tuple[dict, ...] = field(default_factory=tuple)
    audit_events_after: tuple[dict, ...] = field(default_factory=tuple)

    @property
    def stdout_json(self) -> dict:
        """Parse the single-line JSON verdict from stdout, or {} if absent.

        Returns empty dict (not None) so step bodies can call `.get(...)`
        without conditional unwrap.
        """
        for line in self.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
        return {}

    @property
    def new_bypass_events(self) -> tuple[dict, ...]:
        """The SpineBypassUsed events emitted by this invocation only."""
        before_ids = {id(e) for e in self.audit_events_before}
        return tuple(
            e
            for e in self.audit_events_after
            if id(e) not in before_ids and e.get("event") == _BYPASS_EVENT
        )


class KillSwitchFixture:
    """Drives the spine-ledger gate subprocess against a tmp_path target.

    Each instance is bound to one tmp_path target tree (passed in). The
    fixture exposes composition methods that step bodies invoke; no business
    logic is inlined in any step.
    """

    def __init__(self, target_root: Path) -> None:
        self._target_root = target_root
        self._target_root.mkdir(parents=True, exist_ok=True)
        self._commit_msg_path = self._target_root / "candidate-commit-msg.txt"

    # ---- Precondition setup (Given step delegates) ----

    def ensure_telemetry_dir_with_zero_verified_slices(self) -> None:
        """Create `.nwave/telemetry/atdd-pure/` empty (no verified slices)."""
        (self._target_root / _TELEMETRY_RELPATH).mkdir(parents=True, exist_ok=True)

    def ensure_no_telemetry_dir(self) -> None:
        """Guarantee `.nwave/telemetry/atdd-pure/` does NOT exist on the target.

        Dormant-mode precondition for AT-3.
        """
        telemetry_dir = self._target_root / _TELEMETRY_RELPATH
        assert not telemetry_dir.exists(), (
            "Test author error: tmp_path target should be clean by construction."
        )

    def set_bypass_env(self, value: str = "1") -> None:
        """Set NWAVE_SPINE_LEDGER_GATE_BYPASS in the process environment."""
        os.environ[_BYPASS_ENV] = value

    def clear_bypass_env(self) -> None:
        """Remove NWAVE_SPINE_LEDGER_GATE_BYPASS from the process environment."""
        os.environ.pop(_BYPASS_ENV, None)

    def write_disabled_gates_file_naming_spine_gate(self) -> None:
        """Write `.nwave/disabled-gates` listing `spine-ledger-gate` on its own line."""
        path = self._target_root / _DISABLED_GATES_RELPATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{_GATE_NAME}\n", encoding="utf-8")

    def ensure_no_disabled_gates_file(self) -> None:
        """Guarantee `.nwave/disabled-gates` does NOT exist on the target."""
        path = self._target_root / _DISABLED_GATES_RELPATH
        assert not path.exists(), (
            "Test author error: tmp_path target should be clean by construction."
        )

    def write_candidate_commit_message_with_slice_trailer(self, slice_id: str) -> None:
        """Write a candidate commit message carrying `Slice-Id: <slice_id>`."""
        self._commit_msg_path.write_text(
            f"chore(test): synthetic candidate commit\n\nSlice-Id: {slice_id}\n",
            encoding="utf-8",
        )

    # ---- Action (When step delegates) ----

    def run_gate(self) -> GateInvocation:
        """Invoke the production gate script as a real subprocess against the target.

        Reads the audit log before + after so we can compute the delta of new
        SpineBypassUsed events (Mandate 8 universe-bound state delta).
        """
        before_events = self._read_audit_log_events()
        # In-process analogue of `python -m scripts.hooks.spine_ledger_gate`
        # (corpus-migration): drive the production CLI EDGE `main(argv)` under
        # the repo root, capturing stdout/stderr. The original fork passed
        # `env={**os.environ}` (an unmodified copy) -- in-process os.environ is
        # already that same env, so no env juggling is needed here.
        exit_code, stdout, stderr = run_cli_in_process(
            [
                "--commit-msg-file",
                str(self._commit_msg_path),
                "--ledger-root",
                str(self._target_root / _TELEMETRY_RELPATH),
                "--target-root",
                str(self._target_root),
            ],
            cwd=_REPO_ROOT,
            main=spine_ledger_gate.main,
        )
        after_events = self._read_audit_log_events()
        return GateInvocation(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            audit_events_before=before_events,
            audit_events_after=after_events,
        )

    # ---- Observation (Then step delegates) ----

    def assert_verdict_allowed(self, invocation: GateInvocation) -> None:
        """Assert the gate exited with `commit-allowed`.

        Surfaces a clear AssertionError when the subprocess crashed (RED-for-
        right-reason on a missing target script).
        """
        assert invocation.exit_code == 0, (
            f"Expected the gate to exit 0 (commit-allowed); got exit "
            f"{invocation.exit_code}.\nstdout: {invocation.stdout!r}\n"
            f"stderr: {invocation.stderr!r}"
        )
        verdict = invocation.stdout_json.get("verdict")
        assert verdict == "commit-allowed", (
            f"Expected stdout JSON verdict 'commit-allowed'; got {verdict!r}.\n"
            f"stdout: {invocation.stdout!r}"
        )

    def assert_bypass_cause(self, invocation: GateInvocation, cause: str) -> None:
        """Assert the gate's stdout JSON reports the named bypass/dormant cause."""
        actual = invocation.stdout_json.get("cause")
        assert actual == cause, (
            f"Expected stdout JSON cause {cause!r}; got {actual!r}.\n"
            f"stdout: {invocation.stdout!r}"
        )

    def assert_exactly_one_new_bypass_event(self, invocation: GateInvocation) -> None:
        """Assert the audit log gained exactly one new SpineBypassUsed event."""
        count = len(invocation.new_bypass_events)
        assert count == 1, (
            f"Expected exactly 1 new {_BYPASS_EVENT} audit event; got {count}.\n"
            f"new events: {invocation.new_bypass_events!r}"
        )

    def assert_zero_new_bypass_events(self, invocation: GateInvocation) -> None:
        """Assert the audit log gained zero new SpineBypassUsed events."""
        count = len(invocation.new_bypass_events)
        assert count == 0, (
            f"Expected zero new {_BYPASS_EVENT} audit events (dormant-mode); "
            f"got {count}.\nnew events: {invocation.new_bypass_events!r}"
        )

    def assert_bypass_event_source(
        self, invocation: GateInvocation, source: str
    ) -> None:
        """Assert the (single) new bypass event names the given bypass source."""
        events = invocation.new_bypass_events
        assert len(events) == 1, (
            f"assert_bypass_event_source requires exactly one new event; "
            f"got {len(events)}."
        )
        actual = events[0].get("bypass_source")
        assert actual == source, (
            f"Expected bypass_source {source!r}; got {actual!r}.\nevent: {events[0]!r}"
        )

    def assert_bypass_event_names_slice(
        self, invocation: GateInvocation, slice_id: str
    ) -> None:
        """Assert the (single) new bypass event carries the candidate slice id."""
        events = invocation.new_bypass_events
        assert len(events) == 1, (
            f"assert_bypass_event_names_slice requires exactly one new event; "
            f"got {len(events)}."
        )
        actual = events[0].get("candidate_slice")
        assert actual == slice_id, (
            f"Expected candidate_slice {slice_id!r}; got {actual!r}.\n"
            f"event: {events[0]!r}"
        )

    def assert_filesystem_unchanged_outside_audit_log(self) -> None:
        """Assert dormant-mode leaves no telemetry dir, no disabled-gates file.

        Universe-bound to the surfaces the slice-00 contract owns: the
        absence of `.nwave/telemetry/atdd-pure/` and `.nwave/disabled-gates`
        is part of the dormant-mode precondition; the gate MUST NOT create
        either as a side effect.
        """
        assert not (self._target_root / _TELEMETRY_RELPATH).exists(), (
            "Dormant-mode gate MUST NOT create .nwave/telemetry/atdd-pure/."
        )
        assert not (self._target_root / _DISABLED_GATES_RELPATH).exists(), (
            "Dormant-mode gate MUST NOT create .nwave/disabled-gates."
        )

    # ---- Internal helpers ----

    def _audit_log_path(self) -> Path:
        """Return today's audit log path under the target root."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self._target_root / _AUDIT_LOG_DIR_RELPATH / f"audit-{today}.log"

    def _read_audit_log_events(self) -> tuple[dict, ...]:
        """Parse today's audit log into a tuple of event dicts (empty if absent).

        The file format is JSONL per `JsonlAuditLogWriter`; one event per
        line. Lines that fail to parse are skipped silently (defensive: the
        gate may not have written the file yet on first invocation).
        """
        path = self._audit_log_path()
        if not path.exists():
            return ()
        events: list[dict] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return tuple(events)


# ---------------------------------------------------------------------------
# Slice-01: ledger-evidence block path
# ---------------------------------------------------------------------------
#
# RED-for-the-right-reason: the slice-00 gate script EXISTS but only ships the
# kill-switch + dormant + `slice-00-block-path-deferred` stub branch. The
# slice-01 block path (`commit-refused` + `block-ledger-evidence-missing`) and
# the positive ledger-evidence-present path do NOT exist yet -- the crafter
# will refactor `verify_slice_ledger_record.py` logic INTO `spine_ledger_gate`
# via a helper callable from `_dispatch_block_path`, reusing
# `AtCompletionLedger.read_records` as the single source of truth (Mandate-12
# SSOT-for-ledger-reading constraint, NO duplicated ledger reader).
#
# When the composition fixture invokes the gate for an AT-1 scenario (telemetry
# dir present, NO matching record), the current stub returns
# `{verdict: commit-allowed, cause: slice-00-block-path-deferred}` -- the AT
# assertion `assert_verdict_refused` then fires AssertionError because the
# slice-01 contract expects exit 1 + `block-ledger-evidence-missing`. That is
# the correct RED: the assertion fires because the slice-01 block path is
# unimplemented, not because of an import error or fixture setup bug.
#
# AT-3 (partial-failure-tolerance) seeds one VALID record (via the real
# `AtCompletionLedger` writer, so the M7 contract -- seq + record_hash --
# is satisfied) plus one MALFORMED legacy record (raw bytes lacking `seq` and
# `record_hash`). The slice-01 production helper MUST wrap the per-file
# `read_records` call in try/except `LedgerIntegrityViolation`, emit one
# `LedgerSkipped` audit event per malformed file, and continue scanning. AT-3
# verifies both surfaces: the verdict (allowed -- the valid ledger contains
# the slice) AND the audit event presence + content.


# Where the slice-01 production helper looks for ledger evidence under the
# target root. Mirrors the existing `verify_slice_ledger_record.py` convention
# (`.nwave/telemetry/atdd-pure/<feature_id>.jsonl`) and the slice-00 fixture's
# `_TELEMETRY_RELPATH`.
_LEDGER_SKIPPED_EVENT = "LedgerSkipped"
_LEDGER_INTEGRITY_VIOLATION_CAUSE = "ledger-integrity-violation"


def _seed_verified_slice_record(
    target_root: Path, feature_id: str, slice_id: str
) -> None:
    """Append one M7-shape `SliceCommitVerified` record to a per-feature ledger.

    Uses the real `AtCompletionLedger` writer so the record carries the
    M7 contract (seq + record_hash + timestamp); slice-01 production code
    MUST read through `AtCompletionLedger.read_records` (Mandate-12 SSOT),
    so the seeding MUST go through the same writer to satisfy the same
    contract. Bootstrap the `des` package on `sys.path` because composition
    fixtures invoke ledger seeding directly (the GATE itself goes through
    subprocess; the SEEDING is a test-harness setup helper, not the SUT).
    """
    repo_root = _REPO_ROOT
    src_path = repo_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    from des.adapters.driven.logging.at_completion_ledger import (  # type: ignore[import-not-found]
        AtCompletionLedger,
    )

    ledger = AtCompletionLedger(feature_id, target_root)
    ledger.append_gate_event(event="SliceCommitVerified", slice_id=slice_id)


def _seed_malformed_legacy_ledger(target_root: Path, filename: str) -> Path:
    """Write a pre-M7 legacy ledger file (raw line, no seq/record_hash).

    Mirrors the empirical anchor from Phase 0 audit
    (`atdd-pure-spine-hardening.jsonl`: 1 line, pre-M7 `ATReviewVerdict` with
    no `seq` field). The slice-01 production helper MUST tolerate this file
    via try/except `LedgerIntegrityViolation` + `LedgerSkipped` audit event +
    continue scanning sibling files. Returns the absolute path of the seeded
    malformed file so the AT can assert audit-event content.
    """
    telemetry_dir = target_root / _TELEMETRY_RELPATH
    telemetry_dir.mkdir(parents=True, exist_ok=True)
    malformed_path = telemetry_dir / filename
    # A pre-M7 shape: no `seq`, no `record_hash` -- exactly what the M7
    # fail-closed read rejects as `malformed-line` (missing required field).
    malformed_record = {
        "event": "ATReviewVerdict",
        "feature_id": "legacy-fixture",
        "slice_id": "slice-legacy",
        "timestamp": "2026-05-20T19:53:00Z",
    }
    malformed_path.write_text(
        json.dumps(malformed_record, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return malformed_path


class LedgerEvidenceFixture(KillSwitchFixture):
    """Drives the spine-ledger gate against a tmp_path target for slice-01.

    Extends `KillSwitchFixture` (slice-00) -- inherits all kill-switch
    precondition + observation methods (set/clear bypass env, write
    disabled-gates file, ensure clean target, run gate subprocess). Adds
    only the slice-01-specific surfaces:

      * `seed_verified_slice_record` -- write a healthy M7-shape record via
        `AtCompletionLedger` so the slice-01 read path (which the crafter
        will also route through `AtCompletionLedger.read_records`) sees it
        as verified.
      * `seed_malformed_legacy_ledger` -- write a pre-M7 legacy file with no
        seq/record_hash so the slice-01 read path raises
        `LedgerIntegrityViolation`, which the production helper MUST tolerate
        per Phase 0 audit Gap B fix option 2.

    The seeded malformed-file paths are captured as instance state so AT
    observations (`assert_skipped_file_path_contains`) can refer back to them
    without re-deriving the path inside step bodies (Mandate-12 criterion 3
    -- step bodies stay ≤2 statements with the final statement delegating).
    """

    def __init__(self, target_root: Path) -> None:
        super().__init__(target_root)
        self._seeded_malformed_files: list[Path] = []

    # ---- Precondition setup (Given step delegates) ----

    def seed_verified_slice_record(self, feature_id: str, slice_id: str) -> None:
        """Append a healthy SliceCommitVerified record under the named feature."""
        self.ensure_telemetry_dir_with_zero_verified_slices()
        _seed_verified_slice_record(self._target_root, feature_id, slice_id)

    def seed_malformed_legacy_ledger(self, filename: str) -> None:
        """Write a pre-M7 legacy ledger file under the spine-telemetry directory."""
        path = _seed_malformed_legacy_ledger(self._target_root, filename)
        self._seeded_malformed_files.append(path)

    # ---- Observation (Then step delegates) ----

    def assert_verdict_refused(self, invocation: GateInvocation) -> None:
        """Assert the gate exited 1 with `commit-refused`.

        Surfaces a clear AssertionError when the subprocess returned the
        slice-00 stub verdict (`commit-allowed` + `slice-00-block-path-
        deferred`). That is the RED-for-the-right-reason for AT-1: the
        slice-01 block path is unimplemented.
        """
        assert invocation.exit_code == 1, (
            f"Expected the gate to exit 1 (commit-refused); got exit "
            f"{invocation.exit_code}.\nstdout: {invocation.stdout!r}\n"
            f"stderr: {invocation.stderr!r}"
        )
        verdict = invocation.stdout_json.get("verdict")
        assert verdict == "commit-refused", (
            f"Expected stdout JSON verdict 'commit-refused'; got {verdict!r}.\n"
            f"stdout: {invocation.stdout!r}"
        )

    def assert_refusal_cause(self, invocation: GateInvocation, cause: str) -> None:
        """Assert the gate's stdout JSON reports the named refusal cause."""
        actual = invocation.stdout_json.get("cause")
        assert actual == cause, (
            f"Expected stdout JSON cause {cause!r}; got {actual!r}.\n"
            f"stdout: {invocation.stdout!r}"
        )

    def assert_allow_cause(self, invocation: GateInvocation, cause: str) -> None:
        """Assert the gate's stdout JSON reports the named allow cause.

        Distinct from `assert_bypass_cause` (slice-00) -- this is the slice-01
        positive path where evidence was found in the ledger, not a bypass.
        """
        actual = invocation.stdout_json.get("cause")
        assert actual == cause, (
            f"Expected stdout JSON cause {cause!r}; got {actual!r}.\n"
            f"stdout: {invocation.stdout!r}"
        )

    def assert_stdout_names_unverified_slice(
        self, invocation: GateInvocation, slice_id: str
    ) -> None:
        """Assert the refusal verdict names the unverified slice in stdout JSON.

        The slice-01 verdict shape (per Mandate-12 SSOT, reusing
        `verify_slice_ledger_record.py` conventions) carries the unverified
        slice ids under a `unverified_slices` array or a `slice_id` scalar
        field. The AT tolerates either shape so the crafter has flexibility
        on the exact JSON key name.
        """
        payload = invocation.stdout_json
        unverified = payload.get("unverified_slices")
        scalar = payload.get("slice_id")
        if isinstance(unverified, list):
            assert slice_id in unverified, (
                f"Expected {slice_id!r} in 'unverified_slices' list; "
                f"got {unverified!r}.\nstdout: {invocation.stdout!r}"
            )
            return
        assert scalar == slice_id, (
            f"Expected stdout JSON to name unverified slice {slice_id!r} "
            f"(via 'unverified_slices' list or 'slice_id' scalar); "
            f"got unverified_slices={unverified!r}, slice_id={scalar!r}.\n"
            f"stdout: {invocation.stdout!r}"
        )

    def assert_stdout_names_verified_slice(
        self, invocation: GateInvocation, slice_id: str
    ) -> None:
        """Assert the allow verdict names the verified slice in stdout JSON.

        Tolerates either a `verified_slices` array or a `slice_id` scalar
        field, mirroring `assert_stdout_names_unverified_slice` for the
        positive path.
        """
        payload = invocation.stdout_json
        verified = payload.get("verified_slices")
        scalar = payload.get("slice_id")
        if isinstance(verified, list):
            assert slice_id in verified, (
                f"Expected {slice_id!r} in 'verified_slices' list; "
                f"got {verified!r}.\nstdout: {invocation.stdout!r}"
            )
            return
        assert scalar == slice_id, (
            f"Expected stdout JSON to name verified slice {slice_id!r} "
            f"(via 'verified_slices' list or 'slice_id' scalar); "
            f"got verified_slices={verified!r}, slice_id={scalar!r}.\n"
            f"stdout: {invocation.stdout!r}"
        )

    def assert_stdout_lists_skipped_file_containing(
        self, invocation: GateInvocation, filename_fragment: str
    ) -> None:
        """Assert the stdout JSON reports a skipped ledger file path fragment.

        The slice-01 verdict carries a `ledger_skipped` array (per dispatch
        prompt design) listing the absolute paths of malformed ledger files.
        AT-3 verifies the array contains a path containing the seeded
        legacy filename fragment.
        """
        skipped = invocation.stdout_json.get("ledger_skipped")
        assert isinstance(skipped, list), (
            f"Expected stdout JSON 'ledger_skipped' to be a list; "
            f"got {skipped!r}.\nstdout: {invocation.stdout!r}"
        )
        match_found = any(filename_fragment in entry for entry in skipped)
        assert match_found, (
            f"Expected at least one 'ledger_skipped' entry to contain "
            f"{filename_fragment!r}; got {skipped!r}."
        )

    def assert_exactly_one_new_ledger_skipped_event(
        self, invocation: GateInvocation
    ) -> None:
        """Assert the audit log gained exactly one new LedgerSkipped event."""
        new_events = self._new_audit_events_of_type(invocation, _LEDGER_SKIPPED_EVENT)
        assert len(new_events) == 1, (
            f"Expected exactly 1 new {_LEDGER_SKIPPED_EVENT} audit event; "
            f"got {len(new_events)}.\nnew events: {new_events!r}"
        )

    def assert_ledger_skipped_event_names_path_containing(
        self, invocation: GateInvocation, filename_fragment: str
    ) -> None:
        """Assert the (single) new LedgerSkipped event names a path fragment."""
        new_events = self._new_audit_events_of_type(invocation, _LEDGER_SKIPPED_EVENT)
        assert len(new_events) == 1, (
            f"assert_ledger_skipped_event_names_path_containing requires "
            f"exactly one new event; got {len(new_events)}."
        )
        path_field = new_events[0].get("ledger_path", "")
        assert filename_fragment in str(path_field), (
            f"Expected LedgerSkipped event ledger_path to contain "
            f"{filename_fragment!r}; got {path_field!r}.\n"
            f"event: {new_events[0]!r}"
        )

    def assert_ledger_skipped_event_cause(
        self, invocation: GateInvocation, cause: str
    ) -> None:
        """Assert the (single) new LedgerSkipped event names the named skip cause."""
        new_events = self._new_audit_events_of_type(invocation, _LEDGER_SKIPPED_EVENT)
        assert len(new_events) == 1, (
            f"assert_ledger_skipped_event_cause requires exactly one new event; "
            f"got {len(new_events)}."
        )
        actual = new_events[0].get("cause")
        assert actual == cause, (
            f"Expected LedgerSkipped event cause {cause!r}; got {actual!r}.\n"
            f"event: {new_events[0]!r}"
        )

    # ---- Internal helpers ----

    @staticmethod
    def _new_audit_events_of_type(
        invocation: GateInvocation, event_type: str
    ) -> tuple[dict, ...]:
        """Audit events emitted by this invocation only, filtered by event type.

        Mirrors `GateInvocation.new_bypass_events` but parameterized on the
        event type so slice-01 can target `LedgerSkipped` while slice-00's
        `new_bypass_events` accessor stays bound to `SpineBypassUsed`.
        """
        before_ids = {id(e) for e in invocation.audit_events_before}
        return tuple(
            e
            for e in invocation.audit_events_after
            if id(e) not in before_ids and e.get("event") == event_type
        )


# ---------------------------------------------------------------------------
# Slice-02: PreToolUse hook wiring on Bash
# ---------------------------------------------------------------------------
#
# Slice-02 introduces a NEW hook script `scripts/hooks/spine_ledger_pre_commit_hook.py`
# that wraps the slice-00+01 `spine_ledger_gate.py` for Claude Code's PreToolUse
# protocol on the `Bash` matcher. The hook:
#
#   1. Reads JSON from stdin (Claude Code hook event payload).
#   2. Extracts `tool_input.command` (the Bash command string).
#   3. Shell-fast-path skip: if the command does NOT match `^\s*git\s+commit\b`,
#      exit 0 silently (NO gate spawn, perf <50ms target). Mirrors the
#      `_BASH_EXECUTION_LOG_GUARD` two-tier pattern in `scripts/shared/hook_definitions.py`.
#   4. Commit path: parse the commit-message source from the bash command (`-F <file>`,
#      `-m "..."`, or default `.git/COMMIT_EDITMSG`), invoke `spine_ledger_gate.py`
#      with the resolved message file, capture the gate's verdict.
#   5. On gate exit 0 (allow): exit 0 silently (Claude Code allows the Bash invocation).
#   6. On gate exit 1 (refuse): print `{decision: "block", reason: "..."}` on stdout,
#      exit 2 (Claude Code refuses the Bash invocation per the PreToolUse contract).
#
# RED-for-the-right-reason: the slice-02 hook script
# `scripts/hooks/spine_ledger_pre_commit_hook.py` does NOT EXIST YET (the crafter
# lands it in DELIVER per the platform architect ordering). When the composition
# fixture invokes the absent script, the subprocess returns a non-zero exit with
# stderr naming the missing module; the AT then surfaces this as AssertionError
# on the first `Then` step that calls `assert_block_decision_returned` or
# `assert_approve_decision_returned`. That is the correct RED: assertion fires
# because the slice-02 hook entry point is unimplemented, not because of an
# import error or fixture setup bug.
#
# Mandate-13 (driving-port-only): the SUT is the PreToolUse hook script invoked
# as a real subprocess with JSON stdin (Layer 3, mirrors Claude Code's actual
# invocation contract). The composition fixture inherits all slice-01 ledger
# seeding helpers (so AT-3 matcher-coexistence can wire a real malformed/empty
# telemetry tree) via the `LedgerEvidenceFixture` parent class.
#
# AT-3 matcher-coexistence empirical spike: Claude Code's hooks.json schema
# permits MULTIPLE registrations per (event, matcher) tuple — each entry in the
# array is executed; ANY entry returning `{decision: block}` blocks the tool
# invocation (the spine-ledger hook's block wins even if the execution-log
# guard returned approve). AT-3 verifies this BY CONSTRUCTION: the slice-02
# hook drives the SUT alone (a real Claude Code session would invoke both;
# the AT simulates by invoking the spine-ledger hook on a command the
# execution-log guard would also approve, and verifies the spine-ledger
# block decision is correctly emitted). The coexistence semantics observed
# empirically are documented in `at-scaffold-notes-slice-02.md`.

_PRE_COMMIT_HOOK_MODULE = "scripts.hooks.spine_ledger_pre_commit_hook"


@dataclass(frozen=True)
class HookInvocation:
    """One captured invocation of the spine-ledger PreToolUse hook subprocess.

    Mirrors `GateInvocation` but specialised for the Claude Code hook protocol:
    the SUT reads JSON from stdin (not CLI flags) and writes a `{decision:
    ..., reason: ...}` JSON object to stdout (not a `{verdict: ..., cause:
    ...}` shape — that lives one layer inside, on the gate subprocess the
    hook spawns when the bash command matches `git commit`).
    """

    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    audit_events_before: tuple[dict, ...] = field(default_factory=tuple)
    audit_events_after: tuple[dict, ...] = field(default_factory=tuple)

    @property
    def stdout_json(self) -> dict:
        """Parse the single-line JSON decision from stdout, or {} if absent.

        The Claude Code PreToolUse hook protocol expects a JSON decision
        object on stdout when the hook blocks; on approve, stdout may be
        empty or absent (the exit code is the signal).
        """
        for line in self.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
        return {}

    @property
    def new_bypass_events(self) -> tuple[dict, ...]:
        """SpineBypassUsed events emitted by this invocation only."""
        before_ids = {id(e) for e in self.audit_events_before}
        return tuple(
            e
            for e in self.audit_events_after
            if id(e) not in before_ids and e.get("event") == _BYPASS_EVENT
        )


class PreToolUseHookFixture(LedgerEvidenceFixture):
    """Drives the spine-ledger PreToolUse hook against a tmp_path target.

    Extends `LedgerEvidenceFixture` (slice-01) — inherits all kill-switch +
    ledger-seeding preconditions (set/clear bypass env, write disabled-gates
    file, seed verified slice records, seed malformed legacy ledgers). Adds
    only the slice-02-specific surfaces:

      * `prepare_bash_event_for_git_commit_with_message_file(slice_id)` —
        synthesises the Claude Code hook-event JSON payload for a Bash tool
        invocation of `git commit -F <staged-msg-file>`. Mirrors what Claude
        Code emits on stdin to PreToolUse hooks.
      * `prepare_bash_event_for_non_commit_command(command)` — synthesises
        the hook-event JSON for a non-git-commit bash command (e.g. `ls -la`).
        Used by AT-2 fast-path-skip verification.
      * `invoke_pre_tool_use_hook()` — invokes the slice-02 hook script as
        a real subprocess, piping the prepared JSON event to stdin. Captures
        stdout, stderr, exit code, and wall-clock duration (for the AT-2
        fast-path budget assertion).
      * Assertion helpers: `assert_block_decision_returned`,
        `assert_approve_decision_returned`, `assert_block_reason_names_cause`,
        `assert_block_reason_names_slice`, `assert_gate_subprocess_not_invoked`,
        `assert_filesystem_unchanged_outside_audit_log_and_hook_logs`.

    The hook protocol contract (Claude Code PreToolUse on Bash):

      stdin = {
        "tool_name": "Bash",
        "tool_input": {"command": "git commit -F /tmp/msg.txt", ...},
        "session_id": "...",
        ...
      }
      stdout (block) = {"decision": "block", "reason": "..."}
      stdout (approve) = "" (empty; exit code 0 is the signal)
      exit 0 = allow tool invocation
      exit 2 = block tool invocation (with stdout JSON for reason)
    """

    def __init__(self, target_root: Path) -> None:
        super().__init__(target_root)
        self._prepared_hook_event: dict | None = None
        self._gate_invocation_marker_file = self._target_root / ".gate-invoked-marker"

    # ---- Precondition setup (Given step delegates) ----

    def prepare_bash_event_for_git_commit_with_message_file(
        self, slice_id: str
    ) -> None:
        """Stage a candidate commit message + prepare the hook-event JSON.

        Writes the candidate commit message to `<target>/candidate-commit-msg.txt`
        (via the inherited `write_candidate_commit_message_with_slice_trailer`
        helper from slice-00/01) and constructs the Claude Code hook-event
        payload simulating `git commit -F <that file>`. The prepared event is
        stored on the fixture for the subsequent `invoke_pre_tool_use_hook`
        action step (Pillar 2 chained-narrative — When step composes Given
        results).
        """
        self.write_candidate_commit_message_with_slice_trailer(slice_id)
        commit_msg_file = self._target_root / "candidate-commit-msg.txt"
        self._prepared_hook_event = {
            "tool_name": "Bash",
            "tool_input": {
                "command": f"git commit -F {commit_msg_file}",
                "description": "Commit staged changes",
            },
            "session_id": "test-session-slice-02",
        }

    def prepare_bash_event_for_non_commit_command(self, command: str) -> None:
        """Prepare the hook-event JSON for a non-git-commit bash command.

        AT-2 fast-path-skip precondition: the slice-02 hook MUST early-exit
        on `tool_input.command` that does not match `^\\s*git\\s+commit\\b`.
        """
        self._prepared_hook_event = {
            "tool_name": "Bash",
            "tool_input": {
                "command": command,
                "description": "Non-commit bash invocation",
            },
            "session_id": "test-session-slice-02",
        }

    def note_pre_existing_bash_guard_registered(self) -> None:
        """Document AT-3 precondition that the execution-log guard coexists.

        No-op composition method: the pre-existing `_BASH_EXECUTION_LOG_GUARD`
        is registered in `scripts/shared/hook_definitions.py:64-73` and is
        always present on installed Claude Code sessions. The AT-3 invariant
        verifies the slice-02 hook's behaviour is correct REGARDLESS of the
        sibling guard's presence; the composition fixture invokes the
        spine-ledger hook in isolation (Layer 3), and the AT documents the
        empirically-observed coexistence semantics in scaffold notes.
        """
        # No filesystem state to seed; this step exists for Pillar 1 readability.
        # The matcher-collision spike result is documented in
        # at-scaffold-notes-slice-02.md (see `prepare_bash_event_for_...`
        # docstring for the hook-event JSON shape).

    # ---- Action (When step delegates) ----

    def invoke_pre_tool_use_hook(self) -> HookInvocation:
        """Invoke the slice-02 PreToolUse hook as a real subprocess.

        Pipes the prepared hook-event JSON (from one of the `prepare_*` Given
        steps) to the hook's stdin, mirroring how Claude Code actually invokes
        PreToolUse hooks on Bash. Captures stdout (decision JSON if blocked),
        stderr (diagnostics), exit code (0 = allow, 2 = block per Claude
        Code's protocol), and wall-clock duration in ms (for AT-2 fast-path
        budget assertion).
        """
        assert self._prepared_hook_event is not None, (
            "Test author error: invoke_pre_tool_use_hook called before a "
            "prepare_bash_event_for_* Given step."
        )
        before_events = self._read_audit_log_events()
        stdin_payload = json.dumps(self._prepared_hook_event)
        from time import perf_counter_ns

        # In-process analogue of the stdin-protocol fork
        # `python -m scripts.hooks.spine_ledger_pre_commit_hook` (corpus-
        # migration): the production hook EDGE `main()` reads the event JSON
        # from sys.stdin, so the driver replaces stdin with the SAME payload the
        # subprocess piped in. The 3 NWAVE_* env vars the original fork passed
        # via `env=` are set on os.environ around the call (save/restore in
        # finally so the shared test process is never left mutated).
        saved_env = dict(os.environ)
        os.environ["NWAVE_SPINE_LEDGER_GATE_TARGET_ROOT"] = str(self._target_root)
        os.environ["NWAVE_SPINE_LEDGER_GATE_LEDGER_ROOT"] = str(
            self._target_root / _TELEMETRY_RELPATH
        )
        os.environ["NWAVE_SPINE_LEDGER_GATE_INVOCATION_MARKER_FILE"] = str(
            self._gate_invocation_marker_file
        )
        start_ns = perf_counter_ns()
        try:
            exit_code, stdout, stderr = run_hook_in_process(
                spine_ledger_pre_commit_hook.main,
                stdin_text=stdin_payload,
                cwd=_REPO_ROOT,
            )
        finally:
            os.environ.clear()
            os.environ.update(saved_env)
        duration_ms = (perf_counter_ns() - start_ns) / 1_000_000
        after_events = self._read_audit_log_events()
        return HookInvocation(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
            audit_events_before=before_events,
            audit_events_after=after_events,
        )

    # ---- Observation (Then step delegates) ----

    def assert_block_decision_returned(self, invocation: HookInvocation) -> None:
        """Assert the hook returned a {decision: block} payload + exit 2.

        Claude Code PreToolUse contract: a blocking hook prints
        `{"decision": "block", "reason": "..."}` on stdout and exits with
        code 2. The composition fixture surfaces a clear AssertionError when
        the slice-02 hook script is unimplemented (subprocess returns
        non-zero from missing-module error, not from a real block decision).
        """
        assert invocation.exit_code == 2, (
            f"Expected the hook to exit 2 (block); got exit "
            f"{invocation.exit_code}.\nstdout: {invocation.stdout!r}\n"
            f"stderr: {invocation.stderr!r}"
        )
        decision = invocation.stdout_json.get("decision")
        assert decision == "block", (
            f"Expected stdout JSON decision 'block'; got {decision!r}.\n"
            f"stdout: {invocation.stdout!r}"
        )

    def assert_approve_decision_returned(self, invocation: HookInvocation) -> None:
        """Assert the hook returned approve (exit 0, stdout empty or absent).

        Claude Code PreToolUse contract: an approving hook exits 0; stdout
        may be empty (exit code is the sole signal) or carry an explicit
        `{decision: approve}` (both accepted per the protocol spec).
        """
        assert invocation.exit_code == 0, (
            f"Expected the hook to exit 0 (approve); got exit "
            f"{invocation.exit_code}.\nstdout: {invocation.stdout!r}\n"
            f"stderr: {invocation.stderr!r}"
        )

    def assert_block_reason_names_cause(
        self, invocation: HookInvocation, cause: str
    ) -> None:
        """Assert the block decision's reason text contains the named cause.

        The hook propagates the gate's `cause` field into the Claude-Code-
        facing reason string so the operator sees the structured failure
        without parsing JSON twice. AT-1 verifies the
        `block-ledger-evidence-missing` cause surfaces.
        """
        reason = invocation.stdout_json.get("reason", "")
        assert cause in reason, (
            f"Expected hook decision reason to contain cause {cause!r}; "
            f"got reason {reason!r}.\nstdout: {invocation.stdout!r}"
        )

    def assert_block_reason_names_slice(
        self, invocation: HookInvocation, slice_id: str
    ) -> None:
        """Assert the block decision's reason text names the unverified slice."""
        reason = invocation.stdout_json.get("reason", "")
        assert slice_id in reason, (
            f"Expected hook decision reason to contain slice id {slice_id!r}; "
            f"got reason {reason!r}.\nstdout: {invocation.stdout!r}"
        )

    def assert_bash_invocation_refused_before_spawn(
        self, invocation: HookInvocation
    ) -> None:
        """Assert the block decision was returned BEFORE git would have run.

        Universe-bound (Mandate 8): the absence of any commit side-effect on
        the target machine (no `.git/` mutations, no working-tree changes).
        The hook's contract is that returning `{decision: block}` to Claude
        Code suppresses the Bash tool invocation entirely — git never runs.
        The fixture asserts this indirectly: the hook subprocess returned a
        block decision (exit 2) and the target tmp_path has no `.git/`
        directory (the AT did not seed one), so any git mutation would have
        surfaced as a subprocess error in stderr.
        """
        # Pillar 1 readability: this assertion documents the contract.
        # The mechanical check is the block decision returned (exit 2 +
        # stdout JSON decision==block), which Claude Code interprets as
        # "do NOT run the tool". The composition fixture cannot intercept
        # Claude Code itself — but the hook's behaviour (block decision
        # returned) is the necessary + sufficient condition for the
        # downstream Bash refusal.
        assert invocation.exit_code == 2, (
            "Expected the hook to refuse the Bash invocation via exit 2 "
            f"(block decision); got exit {invocation.exit_code}.\n"
            f"stdout: {invocation.stdout!r}"
        )

    def assert_gate_subprocess_not_invoked(self, invocation: HookInvocation) -> None:
        """Assert the slice-02 hook did NOT spawn the spine-ledger gate subprocess.

        AT-2 fast-path-skip contract: a non-git-commit bash command MUST be
        approved by the hook WITHOUT spawning the Python gate (the cost of
        a Python interpreter startup is the budget-buster the shell-fast-
        path mirrors `_BASH_EXECUTION_LOG_GUARD` to avoid).

        Mechanism: the slice-02 hook writes a marker file at the path named
        by `NWAVE_SPINE_LEDGER_GATE_INVOCATION_MARKER_FILE` env var IFF it
        spawns the gate subprocess (the env var is set by the fixture to a
        tmp_path file). The AT asserts the marker file does NOT exist after
        the hook returns. The hook's implementation MUST honour this
        contract (the env var is documented in slice-02 scaffold notes).
        """
        _ = invocation  # parameter present for signature uniformity
        assert not self._gate_invocation_marker_file.exists(), (
            "Expected the slice-02 hook to early-exit WITHOUT spawning the "
            "spine-ledger gate subprocess; found gate-invocation marker at "
            f"{self._gate_invocation_marker_file!s}. "
            "The fast-path-skip contract requires the hook to grep the "
            "bash command for `^\\s*git\\s+commit\\b` BEFORE spawning Python."
        )

    def assert_filesystem_unchanged_outside_audit_log_and_hook_logs(
        self, invocation: HookInvocation
    ) -> None:
        """Assert no extra filesystem state was created during approve path.

        AT-2 universe-bound (Mandate 8): the slice-02 hook on a non-commit
        bash command MUST NOT create the spine telemetry dir, the disabled-
        gates file, or the gate-invocation marker. The audit log itself
        remains absent (the hook does not write an audit event on approve;
        only on bypass does slice-00 emit `SpineBypassUsed`).
        """
        _ = invocation
        assert not self._gate_invocation_marker_file.exists(), (
            "AT-2 approve path: gate-invocation marker MUST NOT exist."
        )
        assert not (self._target_root / _DISABLED_GATES_RELPATH).exists(), (
            "AT-2 approve path: .nwave/disabled-gates MUST NOT be created."
        )

    def assert_hook_chain_decision_is_block_with_cause(
        self, invocation: HookInvocation, cause: str
    ) -> None:
        """Assert the spine-ledger hook's block decision is correctly emitted.

        AT-3 matcher-coexistence: in a real Claude Code session, BOTH the
        pre-existing `_BASH_EXECUTION_LOG_GUARD` AND the slice-02 spine-
        ledger hook fire on the Bash matcher. Claude Code's PreToolUse
        protocol semantics: ANY hook returning `{decision: block}` blocks
        the tool invocation; the execution-log guard does NOT block
        `git commit` commands (its `grep -q 'execution-log'` test fails
        on a git-commit command line), so its decision is `approve` (silent
        exit 0). The spine-ledger hook's block decision therefore wins by
        construction.

        The composition fixture verifies the spine-ledger hook in isolation
        — it cannot orchestrate Claude Code's full hook chain. The AT-3
        invariant is that the spine-ledger hook's contract is correct
        WHEN INVOKED ALONGSIDE the execution-log guard; the matcher-
        coexistence semantics are documented in at-scaffold-notes-slice-02.md.
        """
        self.assert_block_decision_returned(invocation)
        self.assert_block_reason_names_cause(invocation, cause)


# ---------------------------------------------------------------------------
# Slice-03: SubagentStop soft-escalation detector
# ---------------------------------------------------------------------------
#
# Slice-03 introduces a NEW hook script `scripts/hooks/spine_ledger_subagent_stop_detector.py`
# that fires on Claude Code's SubagentStop event for every returning sub-agent.
# It is the orchestrator-layer SOFT-escalation complement to slice-02's
# PreToolUse HARD-block: when the orchestrator dispatches a sub-agent via
# Agent.Task and that sub-agent ships code (Edit on src/des/*, Bash
# `git commit ...`) WITHOUT a preceding spine-cleared event in the current
# session ledger, slice-03 emits a structured `SpineBypassDetected` audit
# event so the bypass is OBSERVABLE post-hoc.
#
# Empirical anchor: Phase 0 audit Gap C — `HOOK_TRANSCRIPT_NO_MARKERS=430`
# in audit-2026-05-27.log (RCA §2.2). The existing SubagentStop G_COMMIT
# intercept (subagent_stop_handler.py:1080) only fires when DES markers
# are present; 430 marker-less Agent dispatches in one day flowed past
# unobserved. Slice-03 is the PARTIAL closure of Gap C: it does NOT make
# DES markers mandatory (that is an independent feature per Phase 0 §
# "Scope discipline"), but it DOES make the marker-less code-shipping
# dispatches AUDITABLE.
#
# Driving port (Mandate-13 Layer 3 subprocess): the SUT is the new hook
# script invoked as a real `python -m scripts.hooks.spine_ledger_subagent_stop_detector`
# subprocess with the Claude Code SubagentStop JSON event on stdin
# (`{"agent_transcript_path": "...", "session_id": "...", ...}`). The hook
# reads the transcript at the named path, inspects entries for code-shipping
# tool uses, and emits the audit event to the SAME audit log slice-00/01/02
# write to (`.nwave/des/logs/audit-{today}.jsonl`).
#
# Audit-event schema (per platform architect critical-4 observability gap):
#
#   {
#     "event": "SpineBypassDetected",
#     "timestamp": "<ISO8601 UTC>",
#     "transcript_path": "<absolute path of returning Agent transcript>",
#     "evidence": ["Edit src/des/example_module.py", ...],
#     "cause": "no-spine-event-in-session",
#     "session_id": "<Claude Code session id from hook input>"
#   }
#
# (slice_id is OPTIONAL — included when the transcript carries a DES-SLICE
# marker block; absent for the dominant marker-less class.)
#
# RED-for-the-right-reason: the hook script
# `scripts/hooks/spine_ledger_subagent_stop_detector.py` does NOT EXIST YET
# (the crafter lands it in DELIVER per the platform architect ordering).
# When the composition fixture invokes the absent script as a subprocess,
# the Python interpreter returns a non-zero exit with stderr naming the
# missing module; the fixture surfaces this as AssertionError on the
# first `Then` step (`assert_exactly_one_new_bypass_detected_event` /
# `assert_zero_new_bypass_detected_events`). That is the correct RED:
# the assertion fires because the slice-03 hook entry point is
# unimplemented, not because of an import error or fixture setup bug.
#
# Mandate-13 (driving-port-only): the SUT is the hook script invoked as a
# subprocess with JSON stdin (Claude Code's actual invocation contract).
# Step composition does NOT import production modules; the slice-01
# function-scope `AtCompletionLedger` import (composition.py:355) is
# inherited and remains classified as test-harness writer-side seeding
# per slice-01 scaffold notes — slice-03 introduces ZERO additional
# production imports in step composition.

_SUBAGENT_STOP_DETECTOR_MODULE = "scripts.hooks.spine_ledger_subagent_stop_detector"
_BYPASS_DETECTED_EVENT = "SpineBypassDetected"
_CARPACCIO_GATE_CLEARED_EVENT = "CarpaccioGateCleared"


@dataclass(frozen=True)
class SubagentStopInvocation:
    """One captured invocation of the spine-ledger SubagentStop detector subprocess.

    Mirrors `HookInvocation` (slice-02) but specialised for the
    SubagentStop contract: the SUT writes its observable to the audit log
    (NOT to stdout as a decision); stdout MAY be empty (the audit-log
    delta is the universe-bound surface per Mandate 8). Exit code 0
    = soft-pass (slice-03 is a soft-escalation, NEVER blocks — the sub-
    agent already returned by the time SubagentStop fires).
    """

    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    audit_events_before: tuple[dict, ...] = field(default_factory=tuple)
    audit_events_after: tuple[dict, ...] = field(default_factory=tuple)

    @property
    def new_bypass_detected_events(self) -> tuple[dict, ...]:
        """SpineBypassDetected events emitted by this invocation only."""
        before_ids = {id(e) for e in self.audit_events_before}
        return tuple(
            e
            for e in self.audit_events_after
            if id(e) not in before_ids and e.get("event") == _BYPASS_DETECTED_EVENT
        )


def _write_agent_transcript(
    transcript_path: Path, tool_uses: tuple[tuple[str, str], ...]
) -> None:
    """Write a synthetic Claude Code Agent transcript JSONL file.

    Each `tool_uses` entry is a `(tool_name, tool_input_description)` pair
    rendered as one transcript entry shaped like Claude Code's real
    transcript format: `{"message": {"role": "assistant", "content": [
    {"type": "tool_use", "name": "<tool>", "input": {...}}]}}`.

    The input dict is minimal — slice-03 hook only inspects the tool name
    AND, for Edit, the `file_path` field (to confirm `src/des/` shipping).
    """
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for tool_name, description in tool_uses:
        if tool_name == "Edit":
            tool_input: dict = {
                "file_path": description,
                "old_string": "x",
                "new_string": "y",
            }
        elif tool_name == "Bash":
            tool_input = {"command": description, "description": "synthetic"}
        else:
            tool_input = {"description": description}
        entry = {
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "name": tool_name, "input": tool_input}
                ],
            }
        }
        lines.append(json.dumps(entry))
    transcript_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _seed_carpaccio_gate_cleared_record(
    target_root: Path, feature_id: str, slice_id: str
) -> None:
    """Append one `CarpaccioGateCleared` record via the real ledger writer.

    Slice-03 AT-3 precondition: a session that HAS gone through the
    spine has a `CarpaccioGateCleared` event for the candidate slice
    in `.nwave/telemetry/atdd-pure/<feature_id>.jsonl`. The detector
    hook reads through `AtCompletionLedger.read_records` (Mandate-12
    SSOT — same single ledger reader slice-01 production uses), so
    the seeding MUST go through the same writer for the M7 record
    contract to hold.
    """
    repo_root = _REPO_ROOT
    src_path = repo_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    from des.adapters.driven.logging.at_completion_ledger import (  # type: ignore[import-not-found]
        AtCompletionLedger,
    )

    ledger = AtCompletionLedger(feature_id, target_root)
    ledger.append_gate_event(event=_CARPACCIO_GATE_CLEARED_EVENT, slice_id=slice_id)


class SubagentStopDetectorFixture(PreToolUseHookFixture):
    """Drives the spine-ledger SubagentStop detector against a tmp_path target.

    Extends `PreToolUseHookFixture` (slice-02) — inherits every kill-switch
    + ledger-seeding + bash-event preparation helper from slices 00/01/02.
    Adds only the slice-03-specific surfaces:

      * `write_agent_transcript_with_edit_on_src_des(file_path)` —
        synthesise a returning-Agent transcript JSONL containing one Edit
        tool use on the named src/des path. AT-1 precondition.
      * `write_agent_transcript_with_only_read_grep_glob()` — synthesise a
        returning-Agent transcript JSONL containing only Read/Grep/Glob
        tool uses (no code-shipping). AT-2 precondition.
      * `seed_carpaccio_gate_cleared_event(feature_id, slice_id)` — append
        one `CarpaccioGateCleared` record via `AtCompletionLedger`. AT-3
        precondition.
      * `prepare_subagent_stop_event_for_agent_return()` — synthesise the
        Claude Code SubagentStop hook-event JSON payload pointing at the
        previously-written transcript.
      * `invoke_subagent_stop_hook()` — invoke the slice-03 hook as a real
        subprocess, piping the prepared JSON event to stdin. Captures
        stdout, stderr, exit code, wall-clock duration, audit-log delta.
      * Assertion helpers: `assert_exactly_one_new_bypass_detected_event`,
        `assert_zero_new_bypass_detected_events`,
        `assert_bypass_detected_event_cause`,
        `assert_bypass_detected_event_names_evidence_containing`,
        `assert_bypass_detected_event_carries_transcript_path`,
        `assert_soft_pass_decision_returned`,
        `assert_filesystem_unchanged_outside_audit_log`.

    The hook protocol contract (Claude Code SubagentStop):

      stdin = {
        "agent_transcript_path": "<absolute path to JSONL transcript>",
        "session_id": "...",
        "cwd": "...",
        ...
      }
      stdout (soft-pass) = "" (empty; exit 0 is the signal — slice-03 NEVER blocks)
      exit 0 = always (slice-03 is soft-escalation; the audit-log delta is
                       the universe-bound observable per Mandate 8)
    """

    def __init__(self, target_root: Path) -> None:
        super().__init__(target_root)
        self._agent_transcript_path = self._target_root / "agent-transcript.jsonl"
        self._prepared_subagent_stop_event: dict | None = None

    # ---- Precondition setup (Given step delegates) ----

    def write_agent_transcript_with_edit_on_src_des(self, file_path: str) -> None:
        """Stage a returning-Agent transcript with one Edit on a src/des/ path.

        AT-1 + AT-3 precondition: the returning sub-agent's transcript
        contains a code-shipping signal — an Edit tool use whose
        `file_path` argument matches `src/des/.*`. The detector hook
        scans transcript entries for tool_use blocks and classifies an
        Edit on `src/des/` as code-shipping evidence.
        """
        _write_agent_transcript(self._agent_transcript_path, (("Edit", file_path),))

    def write_agent_transcript_with_only_read_grep_glob(self) -> None:
        """Stage a returning-Agent transcript with only read-only tool uses.

        AT-2 precondition: the returning sub-agent's transcript contains
        ZERO code-shipping signals — only Read/Grep/Glob entries. The
        detector hook scans and finds no Edit-on-src/des and no Bash-
        git-commit; the AT verifies the audit log gains ZERO new
        SpineBypassDetected events.
        """
        _write_agent_transcript(
            self._agent_transcript_path,
            (
                ("Read", "/some/file.md"),
                ("Grep", "pattern"),
                ("Glob", "**/*.py"),
            ),
        )

    def seed_carpaccio_gate_cleared_event(self, feature_id: str, slice_id: str) -> None:
        """Append one CarpaccioGateCleared record via the real ledger writer.

        AT-3 precondition: the current Claude Code session has ALREADY
        gone through the spine for `slice_id` — a `CarpaccioGateCleared`
        event for that slice exists in
        `.nwave/telemetry/atdd-pure/<feature_id>.jsonl`. The detector
        reads through `AtCompletionLedger.read_records` (Mandate-12 SSOT)
        and finds the cleared event, suppressing the bypass-detected
        emission.
        """
        self.ensure_telemetry_dir_with_zero_verified_slices()
        _seed_carpaccio_gate_cleared_record(self._target_root, feature_id, slice_id)

    def prepare_subagent_stop_event_for_agent_return(self) -> None:
        """Construct the Claude Code SubagentStop hook-event JSON payload.

        The payload points the detector at the previously-written
        `agent-transcript.jsonl` so the hook can scan it for code-shipping
        signals. The session_id is a literal test-session string (the
        detector keys on it for grouping per-session bypass events in
        downstream aggregator subcommands; slice-03 itself does not
        depend on cross-session correlation).
        """
        self._prepared_subagent_stop_event = {
            "agent_transcript_path": str(self._agent_transcript_path),
            "session_id": "test-session-slice-03",
            "cwd": str(self._target_root),
        }

    # ---- Action (When step delegates) ----

    def invoke_subagent_stop_hook(self) -> SubagentStopInvocation:
        """Invoke the slice-03 SubagentStop hook as a real subprocess.

        Pipes the prepared SubagentStop hook-event JSON to the hook's
        stdin (mirroring Claude Code's actual SubagentStop invocation).
        Captures stdout (typically empty for soft-pass), stderr
        (diagnostics — missing-module error during RED scaffold), exit
        code (always 0 for slice-03 soft-escalation), wall-clock duration,
        and the audit-log delta (the universe-bound observable per
        Mandate 8 — what the hook actually DID is "wrote N events to
        audit log").
        """
        assert self._prepared_subagent_stop_event is not None, (
            "Test author error: invoke_subagent_stop_hook called before "
            "prepare_subagent_stop_event_for_agent_return."
        )
        before_events = self._read_audit_log_events()
        stdin_payload = json.dumps(self._prepared_subagent_stop_event)
        from time import perf_counter_ns

        # In-process analogue of the stdin-protocol fork
        # `python -m scripts.hooks.spine_ledger_subagent_stop_detector` (corpus-
        # migration): the production hook EDGE `main()` reads the SubagentStop
        # event JSON from sys.stdin. The 2 NWAVE_* env vars are set on os.environ
        # around the call (save/restore in finally).
        saved_env = dict(os.environ)
        os.environ["NWAVE_SPINE_LEDGER_GATE_TARGET_ROOT"] = str(self._target_root)
        os.environ["NWAVE_SPINE_LEDGER_GATE_LEDGER_ROOT"] = str(
            self._target_root / _TELEMETRY_RELPATH
        )
        start_ns = perf_counter_ns()
        try:
            exit_code, stdout, stderr = run_hook_in_process(
                spine_ledger_subagent_stop_detector.main,
                stdin_text=stdin_payload,
                cwd=_REPO_ROOT,
            )
        finally:
            os.environ.clear()
            os.environ.update(saved_env)
        duration_ms = (perf_counter_ns() - start_ns) / 1_000_000
        after_events = self._read_audit_log_events()
        return SubagentStopInvocation(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
            audit_events_before=before_events,
            audit_events_after=after_events,
        )

    # ---- Observation (Then step delegates) ----

    def assert_exactly_one_new_bypass_detected_event(
        self, invocation: SubagentStopInvocation
    ) -> None:
        """Assert the audit log gained exactly one new SpineBypassDetected event.

        AT-1 universe-bound (Mandate 8): the SpineBypassDetected event
        count delta is the primary observable for the soft-escalation
        contract. Surfaces a clear AssertionError when the slice-03
        hook script is unimplemented (the subprocess crashes on missing
        module BEFORE writing any audit event, so the delta is zero
        instead of the expected one).
        """
        count = len(invocation.new_bypass_detected_events)
        assert count == 1, (
            f"Expected exactly 1 new {_BYPASS_DETECTED_EVENT} audit event; "
            f"got {count}.\nstderr: {invocation.stderr!r}\n"
            f"new events: {invocation.new_bypass_detected_events!r}"
        )

    def assert_zero_new_bypass_detected_events(
        self, invocation: SubagentStopInvocation
    ) -> None:
        """Assert the audit log gained zero new SpineBypassDetected events.

        AT-2 (read-only fast-path) + AT-3 (spine-cleared honour) both
        verify the suppression contract: the detector MUST NOT emit
        SpineBypassDetected when (a) the transcript carries no code-
        shipping signal OR (b) the current session has a preceding
        CarpaccioGateCleared event for the candidate slice.
        """
        count = len(invocation.new_bypass_detected_events)
        assert count == 0, (
            f"Expected zero new {_BYPASS_DETECTED_EVENT} audit events; "
            f"got {count}.\nnew events: {invocation.new_bypass_detected_events!r}"
        )

    def assert_bypass_detected_event_cause(
        self, invocation: SubagentStopInvocation, cause: str
    ) -> None:
        """Assert the (single) new bypass-detected event names the given cause."""
        events = invocation.new_bypass_detected_events
        assert len(events) == 1, (
            f"assert_bypass_detected_event_cause requires exactly one new event; "
            f"got {len(events)}."
        )
        actual = events[0].get("cause")
        assert actual == cause, (
            f"Expected SpineBypassDetected event cause {cause!r}; got {actual!r}.\n"
            f"event: {events[0]!r}"
        )

    def assert_bypass_detected_event_names_evidence_containing(
        self, invocation: SubagentStopInvocation, fragment: str
    ) -> None:
        """Assert one evidence entry on the (single) new event contains a fragment.

        AT-1: the structured event carries an `evidence` list whose entries
        are short strings describing the detected code-shipping tool uses
        (e.g. `Edit src/des/example_module.py`, `Bash git commit -m ...`).
        The AT verifies at least one entry contains the named fragment
        (substring match — the crafter has flexibility on exact format).
        """
        events = invocation.new_bypass_detected_events
        assert len(events) == 1, (
            f"assert_bypass_detected_event_names_evidence_containing requires "
            f"exactly one new event; got {len(events)}."
        )
        evidence = events[0].get("evidence")
        assert isinstance(evidence, list), (
            f"Expected SpineBypassDetected event 'evidence' to be a list; "
            f"got {evidence!r}.\nevent: {events[0]!r}"
        )
        match_found = any(fragment in str(entry) for entry in evidence)
        assert match_found, (
            f"Expected at least one 'evidence' entry to contain {fragment!r}; "
            f"got {evidence!r}.\nevent: {events[0]!r}"
        )

    def assert_bypass_detected_event_carries_transcript_path(
        self, invocation: SubagentStopInvocation
    ) -> None:
        """Assert the (single) new event carries the returning Agent's transcript path."""
        events = invocation.new_bypass_detected_events
        assert len(events) == 1, (
            f"assert_bypass_detected_event_carries_transcript_path requires "
            f"exactly one new event; got {len(events)}."
        )
        actual = events[0].get("transcript_path")
        expected = str(self._agent_transcript_path)
        assert actual == expected, (
            f"Expected SpineBypassDetected event transcript_path {expected!r}; "
            f"got {actual!r}.\nevent: {events[0]!r}"
        )

    def assert_soft_pass_decision_returned(
        self, invocation: SubagentStopInvocation
    ) -> None:
        """Assert the hook exited 0 (soft-pass — slice-03 NEVER blocks).

        Claude Code SubagentStop contract for slice-03: the sub-agent has
        ALREADY returned by the time SubagentStop fires; blocking is
        impossible (and undesirable — the soft-escalation surface is the
        audit log, NOT the tool decision). Exit 0 always; observability
        is via the audit-log delta.
        """
        assert invocation.exit_code == 0, (
            f"Expected the hook to exit 0 (soft-pass); got exit "
            f"{invocation.exit_code}.\nstdout: {invocation.stdout!r}\n"
            f"stderr: {invocation.stderr!r}"
        )

    def assert_filesystem_unchanged_outside_audit_log(
        self, invocation: SubagentStopInvocation
    ) -> None:
        """Assert no extra filesystem state was created on the AT-2 fast-path.

        AT-2 universe-bound (Mandate 8): the slice-03 hook on a read-only
        sub-agent transcript MUST NOT create the disabled-gates file, the
        gate-invocation marker (slice-02 surface), or any new audit-log
        events (verified separately via
        `assert_zero_new_bypass_detected_events`). The audit log file
        itself may exist (slice-00/01/02 may have written events into it
        via the shared writer), but no NEW SpineBypassDetected event is
        appended.
        """
        _ = invocation
        assert not (self._target_root / _DISABLED_GATES_RELPATH).exists(), (
            "AT-2 read-only path: .nwave/disabled-gates MUST NOT be created."
        )
        # slice-02 gate-invocation marker MUST NOT be touched by slice-03
        # (slice-03 does NOT spawn the gate subprocess; it only reads the
        # ledger via AtCompletionLedger.read_records).
        assert not self._gate_invocation_marker_file.exists(), (
            "AT-2 read-only path: slice-02 gate-invocation marker MUST NOT "
            "be touched by the slice-03 SubagentStop detector."
        )


# ===========================================================================
# Slice-04: Installer wiring + aggregator subcommand
# ===========================================================================
#
# Layer 3 driving ports:
#
#   AT-1 (install/uninstall round-trip): real `nwave-ai` CLI subprocess via
#     `python -m nwave_ai.cli install --target <tmp_path>` and
#     `python -m nwave_ai.cli uninstall --target <tmp_path>` — exercises the
#     production composition root (the installer plugin registry + DESPlugin
#     install() + uninstall() chains) end-to-end against an isolated target.
#
#   AT-2 (aggregator subcommand): real `des` CLI subprocess via
#     `python -m des verify-slice-ledger-evidence --report --since=<date>`
#     against a tmp_path audit log seeded with synthetic events. Exercises
#     the production CLI dispatcher + the new `verify_slice_ledger_evidence`
#     subcommand module.
#
#   AT-3 (HOOK_EVENTS pin): in-process import of
#     `scripts.shared.hook_definitions.HOOK_EVENTS` — pin assertion + marker
#     prefix detection via `_is_des_command`. Test placement note: this AT
#     is co-located with AT-1 + AT-2 under the slice-04 .feature so the
#     Gherkin narrative reads as one cohesive installer-wiring story. The
#     `hook_definitions.py` module is shared substrate config (not domain
#     code, not adapter code); Mandate-13 permits in-process pin testing of
#     substrate-config modules under the same slice acceptance umbrella
#     because the registry is itself part of the installer's driving
#     composition (the installer reads `HOOK_EVENTS` to emit settings.json).
#     Forbidden-path rule (`tests/des/unit/(?:domain|cli)/*`) does NOT
#     apply — the test ships under `tests/installer/acceptance/.../steps/`.
#
# RED-for-the-right-reason: the slice-04 production wiring does NOT EXIST
# YET. Specifically:
#   - `DES_HOOKS` list in `scripts/install/plugins/des_plugin.py` is absent;
#     `nwave-ai install` propagates the existing `DES_SCRIPTS` but NOT the
#     3 spine-ledger hook scripts → AT-1 fails on the
#     `assert_target_scripts_contain_spine_ledger_hooks` assertion.
#   - The 2 new HOOK_EVENTS entries (PreToolUse/Bash for the spine-ledger
#     pre-commit hook in installer-templated Python form, SubagentStop for
#     the spine-ledger SubagentStop detector) are not registered →
#     `len(HOOK_EVENTS) == 10` still, not 12 → AT-1 + AT-3 fail on the
#     `assert_settings_json_carries_new_spine_ledger_entries` /
#     `assert_post_slice_04_hook_events_count` assertions.
#   - The `verify-slice-ledger-evidence` subcommand is NOT in the `_REGISTRY`
#     tuple in `src/des/cli/__main__.py`; the subcommand module
#     `src/des/cli/verify_slice_ledger_evidence.py` does not exist → AT-2
#     fails on subprocess exit code != 0 with stderr naming the missing
#     subcommand.
#
# That is the correct RED: each `Then` step asserts a missing-functionality
# observation that fires AssertionError on the post-condition (not on setup
# error, not on import error, not on fixture broken).

_NWAVE_AI_CLI_MODULE = "nwave_ai.cli"
_DES_CLI_MODULE = "des"
_AGGREGATOR_SUBCOMMAND = "verify-slice-ledger-evidence"
_SPINE_LEDGER_HOOK_SCRIPTS = (
    "spine_ledger_gate.py",
    "spine_ledger_pre_commit_hook.py",
    "spine_ledger_subagent_stop_detector.py",
)
_PRE_TOOL_USE_SPINE_LEDGER_MARKER = "spine_ledger_pre_commit_hook"
_SUBAGENT_STOP_SPINE_LEDGER_MARKER = "spine_ledger_subagent_stop_detector"
_DES_HOOK_MARKER_PREFIX = "# des-hook:"
# Pre-slice-04 baseline (post slice-02 commit `4dc49fad8`). Used as the
# universe-bound pre-state for AT-3's pin assertion.
_PRE_SLICE_04_HOOK_EVENTS_COUNT = 10
_PRE_SLICE_04_PRE_TOOL_USE_COUNT = 5
_PRE_SLICE_04_SUBAGENT_STOP_COUNT = 2
# Post-slice-04 live-registry totals. slice-04 itself lifted these from the
# pre-state baseline (10/5/2) by +2/+1/+1 -> 12/6/3. A LATER orthogonal
# feature (fix-crafter-stash-structural-mitigation slice-01) added a 4th
# PreToolUse/Bash entry (the git-stash guard), so the LIVE registry carried
# 13/7/3; a further orthogonal addition (nwave-flow-v2-enforcement slice-04
# amendment) registered the UserPromptSubmit wave-active anchor entry, so
# the LIVE registry now carries 14/7/3. A further orthogonal addition (the
# --no-verify reminder guard, Ale 2026-06-26) registered a 5th PreToolUse/Bash
# entry, so the LIVE registry now carries 15/8/3. The slice-04 behavioural
# claim (every spine-ledger entry carries the `# des-hook:` marker) is
# unaffected by any addition; only the absolute live-count pins shift.
_POST_SLICE_04_HOOK_EVENTS_COUNT = 15
_POST_SLICE_04_PRE_TOOL_USE_COUNT = 8
_POST_SLICE_04_SUBAGENT_STOP_COUNT = 3


@dataclass(frozen=True)
class InstallerInvocation:
    """One captured invocation of the `nwave-ai install` / `uninstall` CLI."""

    exit_code: int
    stdout: str
    stderr: str
    settings_json_before: dict = field(default_factory=dict)
    settings_json_after: dict = field(default_factory=dict)
    scripts_dir_listing_before: tuple[str, ...] = field(default_factory=tuple)
    scripts_dir_listing_after: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class AggregatorInvocation:
    """One captured invocation of `des verify-slice-ledger-evidence --report`."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def stdout_json(self) -> dict:
        """Parse the single-line JSON report from stdout, or {} if absent."""
        for line in self.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        return {}


@dataclass(frozen=True)
class HookEventsSnapshot:
    """One frozen-by-import snapshot of `HOOK_EVENTS` for pin assertions."""

    total_count: int
    pre_tool_use_count: int
    subagent_stop_count: int
    pre_tool_use_commands: tuple[str, ...]
    subagent_stop_commands: tuple[str, ...]


def _snapshot_hook_events() -> HookEventsSnapshot:
    """Re-import `scripts.shared.hook_definitions` and snapshot HOOK_EVENTS.

    Forces a fresh import so the snapshot reflects on-disk truth (the
    crafter mutates the module in DELIVER; pin assertions must see the
    post-mutation state).
    """
    import importlib

    import scripts.shared.hook_definitions as hd_mod

    hd_mod = importlib.reload(hd_mod)
    events = hd_mod.HOOK_EVENTS

    def _command_of(hook_event_obj) -> str:
        if hook_event_obj.shell_command is not None:
            return hook_event_obj.shell_command
        return f"{hook_event_obj.event}::{hook_event_obj.action}"

    pre_tool_use = tuple(h for h in events if h.event == "PreToolUse")
    subagent_stop = tuple(h for h in events if h.event == "SubagentStop")
    return HookEventsSnapshot(
        total_count=len(events),
        pre_tool_use_count=len(pre_tool_use),
        subagent_stop_count=len(subagent_stop),
        pre_tool_use_commands=tuple(_command_of(h) for h in pre_tool_use),
        subagent_stop_commands=tuple(_command_of(h) for h in subagent_stop),
    )


def _is_des_marker_command(command: str) -> bool:
    """Delegate to `scripts.shared.hook_definitions._is_des_command` (Mandate-12 SSOT).

    Function-scope import for the same reason slice-01's
    `_seed_verified_slice_record` uses a function-scope `AtCompletionLedger`
    import: the test-harness inspector reads through the same SSOT predicate
    the installer uses for orphan detection on uninstall.
    """
    from scripts.shared.hook_definitions import _is_des_command

    return _is_des_command(command)


class InstallWiringFixture(SubagentStopDetectorFixture):
    """Drives the `nwave-ai install` + `des verify-slice-ledger-evidence` CLIs.

    Extends `SubagentStopDetectorFixture` (slice-03) — inherits every
    kill-switch / ledger-seeding / bash-event / agent-transcript helper
    from slices 00/01/02/03. Adds only the slice-04-specific surfaces:

      * `prepare_clean_install_target()` — create an isolated `~/.claude/`
        target directory + a synthetic pre-existing settings.json with a
        sentinel entry (verifies install/uninstall do NOT clobber it).
      * `seed_synthetic_audit_log_for_aggregator(events_by_date)` — write
        synthetic SliceCommitVerified / CarpaccioGateCleared /
        SpineBypassDetected / SpineBypassUsed events into
        `.nwave/des/logs/audit-{date}.log`.
      * `run_nwave_ai_install()` / `run_nwave_ai_uninstall()` — invoke the
        installer / uninstaller via real subprocess against the prepared
        target. Captures exit code + stdout + stderr + settings.json delta
        + scripts dir listing delta.
      * `run_aggregator_subcommand(since)` — invoke
        `des verify-slice-ledger-evidence --report --since=<date>` via real
        subprocess against the prepared target.
      * `snapshot_hook_events()` — pin-assertion entry point for AT-3.
      * Assertion helpers: `assert_install_exits_ok`,
        `assert_target_scripts_contain_spine_ledger_hooks`,
        `assert_settings_json_carries_new_spine_ledger_entries`,
        `assert_uninstall_exits_ok`,
        `assert_settings_json_has_no_spine_ledger_entries`,
        `assert_target_scripts_contain_zero_spine_ledger_hooks`,
        `assert_settings_sentinel_entry_preserved`,
        `assert_aggregator_exits_ok`,
        `assert_aggregator_stdout_field_equals`,
        `assert_aggregator_filesystem_unchanged`,
        `assert_pre_slice_04_hook_events_count`,
        `assert_post_slice_04_hook_events_count`,
        `assert_pre_slice_04_pre_tool_use_count`,
        `assert_post_slice_04_pre_tool_use_count`,
        `assert_pre_slice_04_subagent_stop_count`,
        `assert_post_slice_04_subagent_stop_count`,
        `assert_every_spine_ledger_entry_carries_des_hook_marker`,
        `assert_is_des_command_predicate_matches_every_spine_ledger_entry`.

    The installer composition root (the SUT for AT-1) is `nwave_ai.cli`'s
    `install` / `uninstall` entry chains, which fan into the plugin registry
    and run `DESPlugin.install()` / `DESPlugin.uninstall()` — exactly the
    production composition root (Pillar 3 — app as in production).

    Skip-marker contract: the step bindings module `test_slice_04_installer_wiring.py`
    carries `pytestmark = pytest.mark.skip(...)` at FILE HEAD per ADR-028 +
    friction #26 lesson; the crafter unskips on A_GREEN_ATS.
    """

    def __init__(self, target_root: Path) -> None:
        super().__init__(target_root)
        # Slice-04 isolates the installer target under `<target_root>/claude-home`
        # so the test never writes to the operator's real `~/.claude/` and so
        # the `nwave-ai install --target <path>` flag has somewhere to point.
        self._installer_target = self._target_root / "claude-home"
        self._installer_settings_path = self._installer_target / "settings.json"
        self._installer_scripts_dir = self._installer_target / "scripts"
        self._sentinel_settings_entry_marker = "# nwave-test-sentinel"
        self._captured_pre_snapshot: HookEventsSnapshot | None = None

    # ---- Precondition setup (Given step delegates) ----

    def prepare_clean_install_target(self) -> None:
        """Stage an isolated `~/.claude/` target with one sentinel settings entry.

        AT-1 precondition: a clean target machine. The sentinel entry under
        a non-DES hook namespace verifies the installer's preservation
        contract (uninstall MUST NOT remove non-DES entries).
        """
        self._installer_target.mkdir(parents=True, exist_ok=True)
        sentinel_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "TestSentinel",
                        "hooks": [
                            {
                                "type": "command",
                                "command": (
                                    f"{self._sentinel_settings_entry_marker} "
                                    "echo non-des-sentinel"
                                ),
                            }
                        ],
                    }
                ]
            }
        }
        self._installer_settings_path.write_text(
            json.dumps(sentinel_settings, indent=2), encoding="utf-8"
        )

    def note_pre_slice_04_hook_events_count(self) -> None:
        """Capture the pre-slice-04 HOOK_EVENTS snapshot as a baseline anchor.

        AT-3 precondition: the test promises to verify the post-slice-04
        delta against this baseline. The actual pin against
        `_PRE_SLICE_04_HOOK_EVENTS_COUNT == 10` happens in the assertion
        helper — this Given step composes the precondition narrative.
        """
        self._captured_pre_snapshot = _snapshot_hook_events()

    def seed_synthetic_audit_log_for_aggregator(
        self, event_name: str, count: int, date: str
    ) -> None:
        """Append `count` synthetic events of `event_name` dated `date` to the log.

        AT-2 precondition. The aggregator subcommand scans the audit log
        directory for events whose timestamp falls on or after `--since`,
        groups by event name, and emits cumulative counts. The composition
        fixture seeds the log via the same JSONL format the production
        `JsonlAuditLogWriter` emits — the aggregator reads through the
        same SSOT format (Mandate-12).
        """
        self.ensure_telemetry_dir_with_zero_verified_slices()
        log_dir = self._target_root / _AUDIT_LOG_DIR_RELPATH
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"audit-{date}.log"
        existing = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
        new_lines = []
        for i in range(count):
            event = {
                "event": event_name,
                "timestamp": f"{date}T12:00:{i:02d}.000000+00:00",
                "synthetic": True,
            }
            new_lines.append(json.dumps(event))
        log_path.write_text(
            existing + ("\n".join(new_lines) + "\n" if new_lines else ""),
            encoding="utf-8",
        )

    # ---- Action (When step delegates) ----

    def run_nwave_ai_install(self) -> InstallerInvocation:
        """Invoke `nwave-ai install --target <claude-home>` as a real subprocess.

        Captures settings.json + scripts dir state before + after so the
        delta is the universe-bound observable for AT-1 (Mandate 8).
        """
        before_settings = self._read_settings_json_or_empty()
        before_scripts = self._read_scripts_dir_listing()
        # In-process analogue of `python -m nwave_ai.cli install --target <p>`
        # (corpus-migration): drive the production install entry chain
        # `_handle_install(argv)` -- the SUT named in this fixture's class
        # docstring (it fans into the plugin registry + DESPlugin.install()).
        # `_handle_install` mutates os.environ["CLAUDE_CONFIG_DIR"] (consumed by
        # its nested install_nwave.py subprocess), so os.environ is saved and
        # restored around the call. Filesystem observables (settings.json +
        # scripts dir delta on the isolated target) are identical to the fork.
        saved_env = dict(os.environ)
        try:
            exit_code, stdout, stderr = run_cli_in_process(
                ["--target", str(self._installer_target)],
                cwd=_REPO_ROOT,
                main=_handle_install,
            )
        finally:
            os.environ.clear()
            os.environ.update(saved_env)
        after_settings = self._read_settings_json_or_empty()
        after_scripts = self._read_scripts_dir_listing()
        return InstallerInvocation(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            settings_json_before=before_settings,
            settings_json_after=after_settings,
            scripts_dir_listing_before=before_scripts,
            scripts_dir_listing_after=after_scripts,
        )

    def run_nwave_ai_uninstall(self) -> InstallerInvocation:
        """Invoke `nwave-ai uninstall --target <claude-home>` as a real subprocess."""
        before_settings = self._read_settings_json_or_empty()
        before_scripts = self._read_scripts_dir_listing()
        # In-process analogue of `python -m nwave_ai.cli uninstall --target <p>`
        # (corpus-migration): drive the production uninstall entry chain
        # `_handle_uninstall(argv)`. Like install, it mutates
        # os.environ["CLAUDE_CONFIG_DIR"] (and implies --force for an explicit
        # target), so os.environ is saved/restored around the call.
        saved_env = dict(os.environ)
        try:
            exit_code, stdout, stderr = run_cli_in_process(
                ["--target", str(self._installer_target)],
                cwd=_REPO_ROOT,
                main=_handle_uninstall,
            )
        finally:
            os.environ.clear()
            os.environ.update(saved_env)
        after_settings = self._read_settings_json_or_empty()
        after_scripts = self._read_scripts_dir_listing()
        return InstallerInvocation(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            settings_json_before=before_settings,
            settings_json_after=after_settings,
            scripts_dir_listing_before=before_scripts,
            scripts_dir_listing_after=after_scripts,
        )

    def run_aggregator_subcommand(self, since: str) -> AggregatorInvocation:
        """Invoke `des verify-slice-ledger-evidence --report --since=<date>`."""
        # In-process analogue of `python -m des verify-slice-ledger-evidence
        # --report --since=<date>` (corpus-migration): drive the production des
        # CLI dispatcher EDGE (the run_cli_in_process default `main`), the same
        # entry `python -m des` reaches. The single NWAVE_* env var is set on
        # os.environ around the call (save/restore in finally).
        saved_env = dict(os.environ)
        os.environ["NWAVE_SPINE_LEDGER_GATE_TARGET_ROOT"] = str(self._target_root)
        try:
            exit_code, stdout, stderr = run_cli_in_process(
                [_AGGREGATOR_SUBCOMMAND, "--report", f"--since={since}"],
                cwd=_REPO_ROOT,
            )
        finally:
            os.environ.clear()
            os.environ.update(saved_env)
        return AggregatorInvocation(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
        )

    def snapshot_hook_events(self) -> HookEventsSnapshot:
        """Re-import `hook_definitions` and snapshot HOOK_EVENTS for pin assertions."""
        return _snapshot_hook_events()

    # ---- Observation (Then step delegates) ----

    def assert_install_exits_ok(self, invocation: InstallerInvocation) -> None:
        """Universe-bound (Mandate 8): the installer subprocess exits 0."""
        assert invocation.exit_code == 0, (
            f"Expected `nwave-ai install` exit 0; got {invocation.exit_code}.\n"
            f"stderr: {invocation.stderr!r}"
        )

    def assert_target_scripts_contain_spine_ledger_hooks(
        self, invocation: InstallerInvocation
    ) -> None:
        """Universe-bound (Mandate 8): the 3 hook scripts land in `~/.claude/scripts/`."""
        listing = set(invocation.scripts_dir_listing_after)
        missing = [name for name in _SPINE_LEDGER_HOOK_SCRIPTS if name not in listing]
        assert not missing, (
            f"Expected all 3 spine-ledger hook scripts in target "
            f"~/.claude/scripts/ post-install; missing: {missing}.\n"
            f"actual listing: {sorted(listing)}"
        )

    def assert_settings_json_carries_new_spine_ledger_entries(
        self, invocation: InstallerInvocation
    ) -> None:
        """Universe-bound: settings.json gains one PreToolUse + one SubagentStop spine-ledger entry."""
        after = invocation.settings_json_after.get("hooks", {})
        pre_tool_use_spine = [
            e
            for e in after.get("PreToolUse", [])
            if any(
                _PRE_TOOL_USE_SPINE_LEDGER_MARKER in h.get("command", "")
                for h in e.get("hooks", [])
            )
        ]
        subagent_stop_spine = [
            e
            for e in after.get("SubagentStop", [])
            if any(
                _SUBAGENT_STOP_SPINE_LEDGER_MARKER in h.get("command", "")
                for h in e.get("hooks", [])
            )
        ]
        assert len(pre_tool_use_spine) == 1, (
            f"Expected exactly 1 new PreToolUse entry naming "
            f"{_PRE_TOOL_USE_SPINE_LEDGER_MARKER!r}; got {len(pre_tool_use_spine)}.\n"
            f"PreToolUse entries: {after.get('PreToolUse', [])!r}"
        )
        assert len(subagent_stop_spine) == 1, (
            f"Expected exactly 1 new SubagentStop entry naming "
            f"{_SUBAGENT_STOP_SPINE_LEDGER_MARKER!r}; got {len(subagent_stop_spine)}.\n"
            f"SubagentStop entries: {after.get('SubagentStop', [])!r}"
        )

    def assert_new_spine_ledger_entries_carry_des_hook_marker(
        self, invocation: InstallerInvocation
    ) -> None:
        """Every newly added spine-ledger entry carries the `# des-hook:` prefix.

        Critical for clean uninstall: the marker is the SSOT predicate
        `_is_des_command` uses to detect DES hooks (slice-04 critical-7).
        """
        after = invocation.settings_json_after.get("hooks", {})
        spine_entries = []
        for event_name in ("PreToolUse", "SubagentStop"):
            for entry in after.get(event_name, []):
                for hook in entry.get("hooks", []):
                    cmd = hook.get("command", "")
                    if "spine_ledger" in cmd:
                        spine_entries.append(cmd)
        missing_marker = [
            cmd for cmd in spine_entries if _DES_HOOK_MARKER_PREFIX not in cmd
        ]
        assert not missing_marker, (
            f"Expected every spine-ledger entry to carry "
            f"{_DES_HOOK_MARKER_PREFIX!r} marker prefix; missing on: "
            f"{missing_marker!r}"
        )

    def assert_uninstall_exits_ok(self, invocation: InstallerInvocation) -> None:
        """Universe-bound: the uninstaller subprocess exits 0."""
        assert invocation.exit_code == 0, (
            f"Expected `nwave-ai uninstall` exit 0; got {invocation.exit_code}.\n"
            f"stderr: {invocation.stderr!r}"
        )

    def assert_settings_json_has_no_spine_ledger_entries(
        self, invocation: InstallerInvocation
    ) -> None:
        """Universe-bound: post-uninstall settings.json carries zero spine-ledger entries."""
        after = invocation.settings_json_after.get("hooks", {})
        remaining = []
        for event_name in ("PreToolUse", "SubagentStop"):
            for entry in after.get(event_name, []):
                for hook in entry.get("hooks", []):
                    cmd = hook.get("command", "")
                    if "spine_ledger" in cmd:
                        remaining.append((event_name, cmd))
        assert not remaining, (
            f"Expected zero spine-ledger entries post-uninstall; remaining: "
            f"{remaining!r}"
        )

    def assert_target_scripts_contain_zero_spine_ledger_hooks(
        self, invocation: InstallerInvocation
    ) -> None:
        """Universe-bound: post-uninstall `~/.claude/scripts/` contains zero spine-ledger scripts."""
        listing = set(invocation.scripts_dir_listing_after)
        remaining = [name for name in _SPINE_LEDGER_HOOK_SCRIPTS if name in listing]
        assert not remaining, (
            f"Expected zero spine-ledger hook scripts in target "
            f"~/.claude/scripts/ post-uninstall; remaining: {remaining}.\n"
            f"actual listing: {sorted(listing)}"
        )

    def assert_settings_sentinel_entry_preserved(
        self, invocation: InstallerInvocation
    ) -> None:
        """Universe-bound: non-DES sentinel entry survives install AND uninstall.

        The sentinel was authored under PreToolUse/TestSentinel matcher in
        `prepare_clean_install_target` with a command carrying the
        `# nwave-test-sentinel` marker (NOT a `# des-hook:` marker). The
        installer's `is_des_hook_entry` predicate MUST NOT match it; the
        uninstaller's filter MUST preserve it.
        """
        after = invocation.settings_json_after.get("hooks", {})
        sentinel_found = any(
            self._sentinel_settings_entry_marker in h.get("command", "")
            for entry in after.get("PreToolUse", [])
            for h in entry.get("hooks", [])
        )
        assert sentinel_found, (
            f"Expected non-DES sentinel entry (marker "
            f"{self._sentinel_settings_entry_marker!r}) to survive uninstall; "
            f"not found in PreToolUse entries: {after.get('PreToolUse', [])!r}"
        )

    def assert_aggregator_exits_ok(self, invocation: AggregatorInvocation) -> None:
        """Universe-bound: the aggregator subprocess exits 0."""
        assert invocation.exit_code == 0, (
            f"Expected `des verify-slice-ledger-evidence` exit 0; "
            f"got {invocation.exit_code}.\nstderr: {invocation.stderr!r}"
        )

    def assert_aggregator_stdout_is_json(
        self, invocation: AggregatorInvocation
    ) -> None:
        """Universe-bound: the aggregator emits parseable JSON to stdout."""
        parsed = invocation.stdout_json
        assert parsed, (
            f"Expected `des verify-slice-ledger-evidence --report` to emit "
            f"parseable JSON to stdout; got stdout: {invocation.stdout!r}"
        )

    def assert_aggregator_stdout_field_equals_string(
        self, invocation: AggregatorInvocation, field_name: str, expected: str
    ) -> None:
        """Universe-bound: the report JSON names `field_name` with the expected string value."""
        actual = invocation.stdout_json.get(field_name)
        assert actual == expected, (
            f"Expected report JSON field {field_name!r} == {expected!r}; "
            f"got {actual!r}.\nfull report: {invocation.stdout_json!r}"
        )

    def assert_aggregator_stdout_field_equals_int(
        self, invocation: AggregatorInvocation, field_name: str, expected: int
    ) -> None:
        """Universe-bound: the report JSON names `field_name` with the expected int value."""
        actual = invocation.stdout_json.get(field_name)
        assert actual == expected, (
            f"Expected report JSON field {field_name!r} == {expected}; "
            f"got {actual!r}.\nfull report: {invocation.stdout_json!r}"
        )

    def assert_aggregator_filesystem_unchanged(
        self, invocation: AggregatorInvocation
    ) -> None:
        """Universe-bound (Mandate 8): the aggregator MUST be read-only.

        It surfaces metrics from the existing audit log; it MUST NOT
        create / mutate any file under the target tree outside transient
        stdout emission. Verified by post-invocation absence of new files
        beyond the seeded audit log directory.
        """
        _ = invocation
        # No new audit-log files; no .nwave/disabled-gates created; no
        # additional telemetry records appended (the seeded log is the
        # only existing audit-log file).
        assert not (self._target_root / _DISABLED_GATES_RELPATH).exists(), (
            "Aggregator MUST be read-only; .nwave/disabled-gates MUST NOT exist."
        )

    def assert_pre_slice_04_hook_events_count(
        self, snapshot: HookEventsSnapshot
    ) -> None:
        """Universe-bound: pre-slice-04 baseline = 10 HOOK_EVENTS entries."""
        assert snapshot.total_count == _PRE_SLICE_04_HOOK_EVENTS_COUNT, (
            f"Expected pre-slice-04 HOOK_EVENTS count == "
            f"{_PRE_SLICE_04_HOOK_EVENTS_COUNT}; got {snapshot.total_count}."
        )

    def assert_post_slice_04_hook_events_count(
        self, snapshot: HookEventsSnapshot
    ) -> None:
        """Universe-bound: post-slice-04 HOOK_EVENTS count == 14 (10 +2 slice-04 +1 git-stash guard +1 UserPromptSubmit anchor)."""
        assert snapshot.total_count == _POST_SLICE_04_HOOK_EVENTS_COUNT, (
            f"Expected post-slice-04 HOOK_EVENTS count == "
            f"{_POST_SLICE_04_HOOK_EVENTS_COUNT}; got {snapshot.total_count}."
        )

    def assert_pre_slice_04_pre_tool_use_count(
        self, snapshot: HookEventsSnapshot
    ) -> None:
        """Universe-bound: pre-slice-04 PreToolUse entries == 5."""
        assert snapshot.pre_tool_use_count == _PRE_SLICE_04_PRE_TOOL_USE_COUNT, (
            f"Expected pre-slice-04 PreToolUse count == "
            f"{_PRE_SLICE_04_PRE_TOOL_USE_COUNT}; "
            f"got {snapshot.pre_tool_use_count}."
        )

    def assert_post_slice_04_pre_tool_use_count(
        self, snapshot: HookEventsSnapshot
    ) -> None:
        """Universe-bound: post-slice-04 PreToolUse entries == 7 (5 +1 slice-04 +1 git-stash guard)."""
        assert snapshot.pre_tool_use_count == _POST_SLICE_04_PRE_TOOL_USE_COUNT, (
            f"Expected post-slice-04 PreToolUse count == "
            f"{_POST_SLICE_04_PRE_TOOL_USE_COUNT}; "
            f"got {snapshot.pre_tool_use_count}."
        )

    def assert_pre_slice_04_subagent_stop_count(
        self, snapshot: HookEventsSnapshot
    ) -> None:
        """Universe-bound: pre-slice-04 SubagentStop entries == 2."""
        assert snapshot.subagent_stop_count == _PRE_SLICE_04_SUBAGENT_STOP_COUNT, (
            f"Expected pre-slice-04 SubagentStop count == "
            f"{_PRE_SLICE_04_SUBAGENT_STOP_COUNT}; "
            f"got {snapshot.subagent_stop_count}."
        )

    def assert_post_slice_04_subagent_stop_count(
        self, snapshot: HookEventsSnapshot
    ) -> None:
        """Universe-bound: post-slice-04 SubagentStop entries == 3 (+1)."""
        assert snapshot.subagent_stop_count == _POST_SLICE_04_SUBAGENT_STOP_COUNT, (
            f"Expected post-slice-04 SubagentStop count == "
            f"{_POST_SLICE_04_SUBAGENT_STOP_COUNT}; "
            f"got {snapshot.subagent_stop_count}."
        )

    def assert_every_spine_ledger_pre_tool_use_entry_carries_des_hook_marker(
        self, snapshot: HookEventsSnapshot
    ) -> None:
        """Every PreToolUse command naming `spine_ledger` carries `# des-hook:`."""
        spine_entries = [
            cmd for cmd in snapshot.pre_tool_use_commands if "spine_ledger" in cmd
        ]
        missing_marker = [
            cmd for cmd in spine_entries if _DES_HOOK_MARKER_PREFIX not in cmd
        ]
        assert not missing_marker, (
            f"Expected every PreToolUse spine_ledger command to carry "
            f"{_DES_HOOK_MARKER_PREFIX!r} marker; missing on: "
            f"{missing_marker!r}"
        )

    def assert_every_spine_ledger_subagent_stop_entry_carries_des_hook_marker(
        self, snapshot: HookEventsSnapshot
    ) -> None:
        """Every SubagentStop command naming `spine_ledger` carries `# des-hook:`."""
        spine_entries = [
            cmd for cmd in snapshot.subagent_stop_commands if "spine_ledger" in cmd
        ]
        missing_marker = [
            cmd for cmd in spine_entries if _DES_HOOK_MARKER_PREFIX not in cmd
        ]
        assert not missing_marker, (
            f"Expected every SubagentStop spine_ledger command to carry "
            f"{_DES_HOOK_MARKER_PREFIX!r} marker; missing on: "
            f"{missing_marker!r}"
        )

    def assert_is_des_command_matches_every_spine_ledger_entry(
        self, snapshot: HookEventsSnapshot
    ) -> None:
        """The shared `_is_des_command` predicate matches every spine-ledger entry."""
        spine_commands = [
            cmd
            for cmd in snapshot.pre_tool_use_commands + snapshot.subagent_stop_commands
            if "spine_ledger" in cmd
        ]
        unmatched = [cmd for cmd in spine_commands if not _is_des_marker_command(cmd)]
        assert not unmatched, (
            f"Expected `_is_des_command` to return True for every spine-ledger "
            f"entry's command; unmatched: {unmatched!r}"
        )

    # ---- Helpers (private) ----

    def _read_settings_json_or_empty(self) -> dict:
        """Read `<claude-home>/settings.json` or return empty dict if absent."""
        if not self._installer_settings_path.exists():
            return {}
        try:
            return json.loads(self._installer_settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _read_scripts_dir_listing(self) -> tuple[str, ...]:
        """Return sorted tuple of file names under `<claude-home>/scripts/`, or ()."""
        if not self._installer_scripts_dir.exists():
            return ()
        return tuple(sorted(p.name for p in self._installer_scripts_dir.iterdir()))
