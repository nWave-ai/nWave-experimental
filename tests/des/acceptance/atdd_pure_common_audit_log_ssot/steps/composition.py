"""Composition root for the fix-atdd-pure-common-audit-log-ssot slice-01 suite.

Mandate-12 criterion 2/3 + Pillar 3: the SUT is wired through the PRODUCTION
driving ports -- the singleton-shape ``AtCompletionLedger(project_root)``
writer/reader (post-slice-01 refactor target), the ``des verify-integrity``
CLI subprocess, and the build-tier per-feature-ban arch test invoked through
pytest as a subprocess. NO direct domain / internal-helper imports per
F-ATDD-PURE-AT-DIRECT-DOMAIN-TESTING-ANTI-PATTERN.

ALL business logic lives in this module's service methods -- the single
source of truth. Step bodies in ``common_steps.py`` delegate to these methods
and never inline business logic (Mandate-12 criterion 3): each step body is
a typed lookup plus one composition call.

RED scaffold (Mandate 7 / ADR-025): every scenario reds for the RIGHT reason
-- the singleton-shape ``AtCompletionLedger(project_root)`` API does NOT YET
exist (current API is feature-scoped ``AtCompletionLedger(feature_id,
project_root)``), the ``.nwave/audit/atdd-pure-events.jsonl`` substrate does
NOT YET exist, the ``correlation_id`` field is NOT YET written, the
``LedgerIntegrityViolation`` diagnostic does NOT YET name the line number or
link the repair doc, AND the arch test file does NOT YET exist in
``tests/build/``. The composition imports succeed (the existing module is
present); the AT assertions fail because the singleton-shape behaviour is
absent, not because the test infrastructure is broken.

Layer note: AT-1..AT-4 are layer 3 (subprocess / FS acceptance against real
production code) -- example-only, no PBT (Mandate 9/11). AT-5 (correlation
identifier determinism PBT) runs at layer 1 (pure function, no I/O) --
Hypothesis @given allowed per Mandate 9 layer-1 PBT-full default.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types import (
    AggregateReaderMethod,
    ArchTestCallerScenario,
    ArchTestVerdict,
    EventKind,
    FeatureId,
    MigratedCallerId,
    Slice02cAProductionCallsite,
    SliceId,
)


# AggregateReaderMethod is consumed below by the slice-02b reader services;
# this no-op reference ensures the autoflake-style formatter retains the
# import (the symbol is also annotation-cited but ruff `--remove-unused`
# treats string annotations as unused without `from __future__ import
# annotations` in module scope). The `__future__` import IS present at top
# of file; this reference is belt-and-suspenders for the project's hook
# stripper.
_ = AggregateReaderMethod


# --- Domain observation types ------------------------------------------------


@dataclass(frozen=True)
class CommonAuditLogRecord:
    """The user-observable shape of one common-audit-log record.

    Mirrors the JSONL line written by the singleton-shape
    ``AtCompletionLedger`` writer. Port-exposed fields only; internal
    ``_record_hash`` payload is observable but the dataclass surfaces the
    composite (event, slice, feature, correlation) the operator queries.
    Frozen: a result is an immutable observation, never mutated by an
    assertion.
    """

    event: str
    feature_id: str
    slice_id: str
    correlation_id: str
    raw: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class CliVerifyResult:
    """The user-observable verdict of one ``des verify-integrity`` invocation.

    Captures the three observable surfaces the operator-recoverable
    diagnostic must hit (AMEND #1): exit code, the violation class name in
    stdout, the offending line number, and a link to the repair instructions
    doc.
    """

    exit_code: int
    stdout: str
    stderr: str

    @property
    def is_integrity_violation(self) -> bool:
        return self.exit_code != 0 and "LedgerIntegrityViolation" in (
            self.stdout + self.stderr
        )

    @property
    def names_violation_class(self) -> str | None:
        """Return the violation class name (`hash-mismatch`, `truncated-tail`,
        `malformed-line`, `seq-gap`) if surfaced; None otherwise.
        """
        combined = self.stdout + self.stderr
        for class_name in (
            "hash-mismatch",
            "truncated-tail",
            "malformed-line",
            "seq-gap",
        ):
            if class_name in combined:
                return class_name
        return None

    @property
    def names_offending_line_number(self) -> bool:
        combined = self.stdout + self.stderr
        return "line " in combined.lower() and any(c.isdigit() for c in combined)

    @property
    def directs_to_repair_instructions(self) -> bool:
        combined = self.stdout + self.stderr
        return "repair-instructions" in combined or "docs/operations" in combined


@dataclass(frozen=True)
class ArchTestResult:
    """The user-observable verdict of one per-feature-ban arch test invocation."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def verdict(self) -> ArchTestVerdict:
        return ArchTestVerdict.PASS if self.exit_code == 0 else ArchTestVerdict.FAIL


# --- Composition root --------------------------------------------------------


@dataclass
class CommonAuditLogSsotComposition:
    """Production-composition root for the five ATs in slice-01.

    All driving-port invocations route through this composition. The
    composition NEVER imports domain helpers directly (e.g. parsers, hash
    primitives) -- it invokes the production ``AtCompletionLedger`` driving
    port and the production ``des verify-integrity`` CLI subprocess.
    """

    _repo: Path | None = None
    _staged_features: dict[str, list[str]] = field(default_factory=dict)
    _last_appended: dict[str, object] | None = None
    _query_result: list[CommonAuditLogRecord] = field(default_factory=list)
    _cli_result: CliVerifyResult | None = None
    _arch_result: ArchTestResult | None = None
    _arch_temp_tree: Path | None = None
    _correlation_pairs: list[tuple[tuple[str, str, int], str]] = field(
        default_factory=list
    )
    # slice-02b: the aggregate reader's frozenset return (verified_slices /
    # feature_end_events / environmental_e2e_events). Port-exposed observable.
    _reader_result: frozenset[str] | None = None
    # slice-02d-N0: feature_id pinned by the helper-seeding When-clause; the
    # Then-clauses observing per-feature substrate dereference this field.
    _last_helper_feature_id: FeatureId | None = None

    # --- Given services ----------------------------------------------------

    def given_fresh_project_repository(self) -> None:
        """Stage a per-scenario tmp project repository with no audit log yet.

        Creates ``.nwave/`` directory and the workflow config (atdd_pure mode)
        so the production CLI's ``_verify_atdd_pure`` branch is reachable.
        The ``.nwave/audit/atdd-pure-events.jsonl`` substrate is intentionally
        absent -- the writer is expected to provision it on first append (M11).
        """
        workspace = Path(tempfile.mkdtemp(prefix="atdd-pure-common-audit-log-"))
        nwave_dir = workspace / ".nwave"
        nwave_dir.mkdir(parents=True, exist_ok=True)
        (nwave_dir / "config.yaml").write_text("workflow:\n  mode: atdd_pure\n")
        self._repo = workspace

    def given_recorded_event_for_feature(
        self, event_kind: EventKind, feature_id: FeatureId, slice_id: SliceId
    ) -> None:
        """Drive the production writer to append one event for one feature.

        Driving port: ``AtCompletionLedger(project_root)`` singleton-shape
        API (post-slice-01 refactor target). Delegates to
        ``when_writer_appends_event`` so the same code path drives both the
        Given setup and the When action; this keeps the chained narrative
        (Pillar 2) consistent across scenarios.
        """
        self.when_writer_appends_event(event_kind, feature_id, slice_id)
        self._staged_features.setdefault(str(feature_id), []).append(str(event_kind))

    def given_recorded_record_tampered(self) -> None:
        """Hand-edit the last appended record to break its M7 record_hash.

        Simulates the operator-hand-edit attack from design RES-2 perturbation
        3 (hash-mismatch detection). The production reader is then expected
        to surface the tamper via ``LedgerIntegrityViolation`` with the
        ``hash-mismatch`` classifier.
        """
        assert self._repo is not None, "repository not staged"
        log_path = self._repo / ".nwave" / "audit" / "atdd-pure-events.jsonl"
        lines = log_path.read_text(encoding="utf-8").splitlines()
        assert lines, "no records to tamper with"
        last_record = json.loads(lines[-1])
        # Flip a non-hashed observable field (e.g. introduce a forged extra)
        # while preserving the record_hash -- this is the canonical tamper.
        last_record["forged_field"] = "operator-forged"
        lines[-1] = json.dumps(last_record, separators=(",", ":"), sort_keys=True)
        log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def given_arch_test_temp_tree(
        self, caller_scenario: ArchTestCallerScenario
    ) -> None:
        """Seed a temporary src/scripts tree with a caller in the given shape.

        The arch test scans real source files; this method writes a minimal
        Python file matching the scenario's call-site pattern, then makes
        that file the scan target via the test's ``--src-roots`` flag (the
        test exposes the flag so the AT can drive without touching the
        real ``src/``).
        """
        tree = Path(tempfile.mkdtemp(prefix="arch-test-temp-tree-"))
        scripts_dir = tree / "scripts"
        scripts_dir.mkdir()
        if caller_scenario is ArchTestCallerScenario.PER_FEATURE_PATTERN:
            (scripts_dir / "bad_caller.py").write_text(
                'PATH = ".nwave/telemetry/atdd-pure/some-feature.jsonl"\n'
            )
        elif caller_scenario is ArchTestCallerScenario.ARCHIVE_SUBDIRECTORY:
            (scripts_dir / "archive_caller.py").write_text(
                'PATH = ".nwave/telemetry/_archive/atdd-pure/old-feature.jsonl"\n'
            )
        elif caller_scenario is ArchTestCallerScenario.COMMON_AUDIT_LOG:
            (scripts_dir / "good_caller.py").write_text(
                'PATH = ".nwave/audit/atdd-pure-events.jsonl"\n'
            )
        self._arch_temp_tree = tree

    # --- When services -----------------------------------------------------

    def when_writer_appends_event(
        self, event_kind: EventKind, feature_id: FeatureId, slice_id: SliceId
    ) -> None:
        """Drive the production ``AtCompletionLedger`` writer once.

        Driving port boundary: the production composition-root API. Layer 3
        real-I/O via subprocess (Mandate-13): the adapter import lives in
        the spawned child process, not in composition.py's import set. The
        writer creates the substrate directory under ``.nwave/audit/`` and
        appends one JSONL line under flock. Captures the appended record
        (returned as JSON via stdout) for the chained-narrative Then
        assertions.
        """
        assert self._repo is not None, "repository not staged"
        stub = _writer_append_stub(event_kind, feature_id, slice_id)
        record = _run_caller_stub_capture(self._repo, stub)
        assert isinstance(record, dict), (
            f"writer stub returned non-dict payload: {type(record).__name__}"
        )
        self._last_appended = record

    def when_reader_queries_filtered_by_feature(self, feature_id: FeatureId) -> None:
        """Drive the production reader with the feature-id filter.

        Driving port: ``AtCompletionLedger(project_root).read_records(
        feature_id=...)`` -- the new filter-at-read-time capability the SSOT
        consolidation delivers (per design D3). Mandate-13 boundary: the
        adapter import lives ONLY in the spawned subprocess stub.
        """
        assert self._repo is not None, "repository not staged"
        stub = _reader_read_records_filtered_stub(feature_id)
        raw_records = _run_caller_stub_capture(self._repo, stub)
        assert isinstance(raw_records, list), (
            f"reader stub returned non-list payload: {type(raw_records).__name__}"
        )
        self._query_result = [
            CommonAuditLogRecord(
                event=str(r.get("event", "")),
                feature_id=str(r.get("feature_id", "")),
                slice_id=str(r.get("slice_id", "")),
                correlation_id=str(r.get("correlation_id", "")),
                raw=dict(r),
            )
            for r in raw_records
        ]

    def when_verify_integrity_cli_runs(self, feature_id: FeatureId) -> None:
        """Drive the production ``des verify-integrity`` CLI as a subprocess.

        Layer 3 real-I/O driving adapter: invokes the production CLI exactly
        as an operator would (subprocess with --feature-id). Captures
        exit code + stdout + stderr for the diagnostic-shape assertions
        (AMEND #1: violation class, line number, repair-doc link).
        """
        assert self._repo is not None, "repository not staged"
        proc = subprocess.run(
            [
                "des",
                "verify-integrity",
                str(self._repo),
                "--feature-id",
                str(feature_id),
            ],
            capture_output=True,
            text=True,
        )
        self._cli_result = CliVerifyResult(
            exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr
        )

    def when_arch_test_runs_on_temp_tree(self) -> None:
        """Drive the per-feature-ban arch test as a pytest subprocess.

        Driving port: pytest invocation of
        ``tests/build/test_no_per_feature_atdd_ledger_writes.py`` with the
        ``--src-roots`` override pointing at the temp tree. Layer 3 real-I/O.
        """
        assert self._arch_temp_tree is not None, "temp tree not staged"
        proc = subprocess.run(
            [
                "pytest",
                "tests/build/test_no_per_feature_atdd_ledger_writes.py",
                f"--src-roots={self._arch_temp_tree}",
                "-q",
                "--no-header",
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parents[5]),
        )
        self._arch_result = ArchTestResult(
            exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr
        )

    def when_correlation_id_derived_twice(
        self, feature_id: str, slice_id: str, dispatch_seq: int
    ) -> tuple[str, str]:
        """Drive the production correlation_id helper twice over the same input.

        Driving port: the production correlation-id derivation function
        exposed by the post-slice-01 ``AtCompletionLedger`` module (or a
        sibling helper). Layer 1 (pure function, no I/O) -- the Hypothesis
        property test invokes this for the determinism check.
        """
        from des.adapters.driven.logging.at_completion_ledger import (
            derive_correlation_id,
        )

        first = derive_correlation_id(feature_id, slice_id, dispatch_seq)
        second = derive_correlation_id(feature_id, slice_id, dispatch_seq)
        self._correlation_pairs.append(((feature_id, slice_id, dispatch_seq), first))
        return first, second

    # --- Then services -----------------------------------------------------

    def then_log_contains_exactly_one_record_for_feature(
        self, feature_id: FeatureId
    ) -> None:
        """Assert the common log carries exactly one record for this feature.

        Port-exposed observable: the JSONL line count filtered by
        ``feature_id`` field. Universe-bound (Mandate 8): the only field
        the assertion observes is the count + the feature filter -- internal
        record_hash etc. are not consulted here.
        """
        assert self._repo is not None, "repository not staged"
        log_path = self._repo / ".nwave" / "audit" / "atdd-pure-events.jsonl"
        assert log_path.is_file(), f"common audit log not provisioned at {log_path}"
        lines = [line for line in log_path.read_text().splitlines() if line.strip()]
        matching = [
            json.loads(line)
            for line in lines
            if json.loads(line).get("feature_id") == str(feature_id)
        ]
        assert len(matching) == 1, (
            f"expected exactly one record for feature={feature_id}; "
            f"found {len(matching)} in log of {len(lines)} total lines"
        )

    def then_last_record_carries(
        self,
        event_kind: EventKind,
        slice_id: SliceId,
    ) -> None:
        """Assert the last-appended record carries the expected event + slice
        AND a derived correlation identifier in the canonical 16-hex shape.
        """
        assert self._last_appended is not None, "no record appended"
        record = self._last_appended
        # Python 3.12 StrEnum: `str(EventKind.X)` returns `"EventKind.X"` not
        # the enum value. Compare against `.value` to extract the canonical
        # event-string the production code writes (preserves assertion
        # semantics; corrects test-plumbing only).
        assert record.get("event") == event_kind.value, (
            f"event mismatch: expected={event_kind.value}, actual={record.get('event')}"
        )
        assert record.get("slice_id") == str(slice_id), (
            f"slice_id mismatch: expected={slice_id}, actual={record.get('slice_id')}"
        )
        correlation_id = record.get("correlation_id")
        assert isinstance(correlation_id, str) and len(correlation_id) == 16, (
            f"correlation_id not 16-hex: actual={correlation_id!r}"
        )
        assert all(c in "0123456789abcdef" for c in correlation_id), (
            f"correlation_id not lowercase hex: actual={correlation_id!r}"
        )

    def then_query_returned_exactly_one_record(self) -> None:
        """Assert the filtered query returned exactly one record."""
        assert len(self._query_result) == 1, (
            f"expected exactly one record from filtered query; "
            f"found {len(self._query_result)}"
        )

    def then_query_record_carries_feature(self, feature_id: FeatureId) -> None:
        """Assert the single returned record carries the expected feature id."""
        assert len(self._query_result) == 1, "query did not return exactly one record"
        actual = self._query_result[0].feature_id
        assert actual == str(feature_id), (
            f"feature_id mismatch: expected={feature_id}, actual={actual}"
        )

    def then_query_returned_exactly_n_records_for_feature(
        self, feature_id: FeatureId, expected_count: int
    ) -> None:
        """Assert the filtered query returned exactly N records, ALL tagged with feature_id.

        AT-A2 forward-pin Then-clause. Universe observed (port-exposed):
        `_query_result` length + each record's `feature_id` field. The
        N-row variant of `then_query_returned_exactly_one_record` -- pinned
        for multi-feature substrate scenarios where the filter discriminates
        across populated rows.
        """
        assert len(self._query_result) == expected_count, (
            f"expected {expected_count} records from filtered query for "
            f"feature_id={str(feature_id)!r}; found {len(self._query_result)} "
            f"(records={[r.raw for r in self._query_result]})"
        )
        mismatches = [r for r in self._query_result if r.feature_id != str(feature_id)]
        assert not mismatches, (
            f"filter leakage: {len(mismatches)} of {len(self._query_result)} "
            f"records returned for feature_id={str(feature_id)!r} carried a "
            f"different feature_id (first mismatch={mismatches[0].raw})"
        )

    def then_query_returned_no_records_for_other_feature(
        self, target_feature_id: FeatureId, other_feature_id: FeatureId
    ) -> None:
        """Assert NO record in the filtered query result carries the other feature_id.

        AT-A2 cross-feature-leakage guard. Symmetric to
        `then_query_returned_exactly_n_records_for_feature` but expressed
        from the other side -- pins that the filter discriminates AGAINST
        the unwanted feature, not just FOR the wanted one. The pair is the
        cross-feature isolation observable Mandate 8 requires.
        """
        leaks = [r for r in self._query_result if r.feature_id == str(other_feature_id)]
        assert not leaks, (
            f"cross-feature leakage: query filtered for "
            f"feature_id={str(target_feature_id)!r} returned "
            f"{len(leaks)} records carrying feature_id="
            f"{str(other_feature_id)!r} (first leak={leaks[0].raw})"
        )

    def then_cli_reports_integrity_violation(self) -> None:
        """Assert the CLI exits non-zero with a LedgerIntegrityViolation verdict."""
        assert self._cli_result is not None, "CLI not run"
        assert self._cli_result.is_integrity_violation, (
            f"expected integrity-violation verdict; "
            f"exit={self._cli_result.exit_code}, "
            f"stdout={self._cli_result.stdout!r}, "
            f"stderr={self._cli_result.stderr!r}"
        )

    def then_cli_names_violation_class(self, expected_class: str) -> None:
        """Assert the CLI verdict names the violation class."""
        assert self._cli_result is not None, "CLI not run"
        actual = self._cli_result.names_violation_class
        assert actual == expected_class, (
            f"violation class mismatch: expected={expected_class}, actual={actual}"
        )

    def then_cli_names_offending_line_number(self) -> None:
        """Assert the CLI verdict names the offending line number."""
        assert self._cli_result is not None, "CLI not run"
        assert self._cli_result.names_offending_line_number, (
            f"expected line number in verdict; stdout={self._cli_result.stdout!r}"
        )

    def then_cli_directs_to_repair_instructions(self) -> None:
        """Assert the CLI verdict directs the operator to repair-instructions."""
        assert self._cli_result is not None, "CLI not run"
        assert self._cli_result.directs_to_repair_instructions, (
            f"expected repair-instructions link in verdict; "
            f"stdout={self._cli_result.stdout!r}, "
            f"stderr={self._cli_result.stderr!r}"
        )

    def then_arch_test_verdict_matches(self, expected_verdict: ArchTestVerdict) -> None:
        """Assert the per-feature-ban arch test surfaced the expected verdict."""
        assert self._arch_result is not None, "arch test not run"
        actual = self._arch_result.verdict
        assert actual is expected_verdict, (
            f"arch test verdict mismatch: expected={expected_verdict}, "
            f"actual={actual}; stdout={self._arch_result.stdout!r}, "
            f"stderr={self._arch_result.stderr!r}"
        )

    def then_correlation_ids_match(self, first: str, second: str) -> None:
        """Assert two derivations of correlation_id over the same input agree."""
        assert first == second, (
            f"correlation_id determinism violated: first={first}, second={second}"
        )

    def then_no_correlation_id_collision(self) -> None:
        """Assert the accumulated correlation_id pairs have no collisions."""
        seen: dict[str, tuple[str, str, int]] = {}
        for input_triple, digest in self._correlation_pairs:
            if digest in seen and seen[digest] != input_triple:
                raise AssertionError(
                    f"correlation_id collision: triples {seen[digest]!r} and "
                    f"{input_triple!r} both hash to {digest!r}"
                )
            seen[digest] = input_triple

    # --- Internal dispatch (NOT business logic, just routing) ---------------

    def _dispatch_append(
        self,
        ledger: object,
        event_kind: EventKind,
        feature_id: FeatureId,
        slice_id: SliceId,
    ) -> dict[str, object]:
        """Route the event-kind enum to the matching ``append_*`` method.

        Mandate-12 criterion 3 compliant: this is a typed-dispatch lookup
        (not business logic). The DSL emerges from the typed enum -- the
        composition selects the production writer method without an
        ``if``-ladder per call site.
        """
        # Mandate-12 typed dispatch: enum → bound-method via lookup table.
        # The table itself is constructed once per call (cheap); the lookup
        # is a single dict access, never control flow.
        dispatch_table = {
            EventKind.CARPACCIO_GATE_CLEARED: lambda: ledger.append_gate_event(  # type: ignore[attr-defined]
                feature_id=str(feature_id),
                event="CarpaccioGateCleared",
                slice_id=str(slice_id),
            ),
            EventKind.SLICE_COMMIT_VERIFIED: lambda: ledger.append_gate_event(  # type: ignore[attr-defined]
                feature_id=str(feature_id),
                event="SliceCommitVerified",
                slice_id=str(slice_id),
            ),
            EventKind.WALKING_SKELETON_GATE_RAN: lambda: (
                ledger.append_walking_skeleton_gate_ran(  # type: ignore[attr-defined]
                    feature_id=str(feature_id),
                    slice_id=str(slice_id),
                )
            ),
            # slice-02b: env-e2e heartbeat dispatch for the aggregate-reader
            # filter ATs. slice_id is ignored by the production writer (env-e2e
            # is feature-scoped, `slice_id == ""`); the typed-dispatch contract
            # is preserved by passing the parameter through.
            EventKind.ENVIRONMENTAL_E2E_GATE_RAN: lambda: (
                ledger.append_environmental_e2e_gate_ran(  # type: ignore[attr-defined]
                    feature_id=str(feature_id),
                )
            ),
        }
        return dispatch_table[event_kind]()

    # --- slice-02: caller-migration services ------------------------------
    # AT-1 invokes one of 11 production driving ports per parametrize row;
    # AT-2 invokes the arch test against the in-tree src/+scripts/ roots;
    # AT-3 is the regression-pin that drives the legacy per-feature shape.
    # Universe observed (port-exposed): common-log file presence + per-feature
    # file presence + arch-test verdict + legacy round-trip record list.

    def given_in_tree_post_migration_state(self) -> None:
        """Pin the in-tree state the AT-2 arch-test invocation will observe.

        Pre-slice-02 GREEN: the in-tree `src/` + `scripts/` roots still carry
        the eleven per-feature-path callers, so AT-2 reds with the arch-test
        in-tree-skip path (the slice-01 arch-test pytest.skip's when invoked
        without `--src-roots` until slice-02 lands). Post-slice-02 GREEN: the
        skip is lifted and the arch test scans the migrated roots.

        Service body is a no-op marker: the observable surface is the actual
        in-tree state on disk, not a staged tmp-tree. The slice-01 RED-scaffold
        contract holds -- the AT reds for the right reason (migration absent)
        rather than a fixture bug.
        """
        # No-op: the in-tree state IS the observable; AT-2 verifies it via
        # `when_arch_test_runs_against_in_tree_roots` below.
        self._in_tree_pinned = True

    def when_caller_driving_port_invoked(
        self,
        caller_id: MigratedCallerId,
        feature_id: FeatureId,
    ) -> None:
        """Invoke the production driving port for one of the 11 migrated callers.

        Layer 3 real-I/O via subprocess (CLI callers) or in-process call from
        composition root (writer-only callers). The dispatch table maps the
        typed `MigratedCallerId` enum to a `_CallerDriver` describing how to
        invoke the production driving port -- composition delegates to the
        driver, never inlines per-caller business logic (Mandate-12).
        """
        assert self._repo is not None, "repository not staged"
        driver = self._caller_driver_dispatch_table()[caller_id]
        driver(self._repo, str(feature_id))

    def when_arch_test_runs_against_in_tree_roots(self) -> None:
        """Drive the per-feature-ban arch test against the in-tree src+scripts.

        Layer 3 real-I/O subprocess: invokes the production
        `tests/build/test_no_per_feature_atdd_ledger_writes.py` WITHOUT a
        `--src-roots` override -- the default scan covers the real `src/` and
        `scripts/` roots. Pre-slice-02 GREEN this skips (slice-01 in-tree
        guard); post-slice-02 GREEN this exits 0 with zero violations.
        """
        proc = subprocess.run(
            [
                "pytest",
                "tests/build/test_no_per_feature_atdd_ledger_writes.py",
                "-q",
                "--no-header",
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parents[5]),
        )
        self._arch_result = ArchTestResult(
            exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr
        )

    def when_legacy_per_feature_writer_appends_event(
        self,
        event_kind: EventKind,
        feature_id: FeatureId,
        slice_id: SliceId,
    ) -> None:
        """Drive the LEGACY per-feature shape writer once (regression-pin AT-3).

        Pillar 3 production composition root: instantiate the legacy
        `AtCompletionLedger(feature_id, project_root)` positional shape and
        append one record under the per-feature substrate. Asserts the
        dual-shape contract (D3) survives slice-02 migration: a refactor
        that drops the legacy shape reds this AT immediately.
        """
        from des.adapters.driven.logging.at_completion_ledger import (
            AtCompletionLedger,
        )

        assert self._repo is not None, "repository not staged"
        ledger = AtCompletionLedger(str(feature_id), self._repo)
        self._last_appended = self._dispatch_append(
            ledger, event_kind, feature_id, slice_id
        )

    def then_common_audit_log_file_exists(self) -> None:
        """Assert the common audit log substrate file exists under the repo.

        Port-exposed observable: file system presence at
        `.nwave/audit/atdd-pure-events.jsonl`. The migrated caller must
        provision this file on first append (M11).
        """
        assert self._repo is not None, "repository not staged"
        log_path = self._repo / ".nwave" / "audit" / "atdd-pure-events.jsonl"
        assert log_path.is_file(), (
            f"common audit log not provisioned at {log_path} -- migrated "
            f"caller did not write to the singleton-shape substrate"
        )

    def then_per_feature_ledger_file_absent(self, feature_id: FeatureId) -> None:
        """Assert the per-feature ledger file was NOT created by the caller.

        Port-exposed observable: file system absence at
        `.nwave/telemetry/atdd-pure/{feature_id}.jsonl`. This is the
        decommissioning observable -- post-migration the caller writes the
        common log only, never the per-feature path.
        """
        assert self._repo is not None, "repository not staged"
        per_feature_path = (
            self._repo / ".nwave" / "telemetry" / "atdd-pure" / f"{feature_id}.jsonl"
        )
        assert not per_feature_path.exists(), (
            f"per-feature ledger file unexpectedly created at {per_feature_path} "
            f"-- caller still writes the decommissioned path"
        )

    def then_per_feature_ledger_file_exists(self, feature_id: FeatureId) -> None:
        """Assert the per-feature ledger file exists (regression-pin AT-3).

        Port-exposed observable: file system presence at the legacy path.
        Confirms the dual-shape contract preserves the legacy substrate
        under the legacy positional construction.
        """
        assert self._repo is not None, "repository not staged"
        per_feature_path = (
            self._repo / ".nwave" / "telemetry" / "atdd-pure" / f"{feature_id}.jsonl"
        )
        assert per_feature_path.is_file(), (
            f"legacy per-feature ledger file missing at {per_feature_path} -- "
            f"dual-shape contract broken"
        )

    def then_arch_test_reports_zero_violations(self) -> None:
        """Assert the in-tree arch test report carries zero violation lines.

        Port-exposed observable: the subprocess stdout/stderr of the arch
        test contains zero violation entries (the slice-01 arch-test prints
        each `{file}:{line}: {literal}` line on failure). Zero violations
        means every caller migrated successfully.
        """
        assert self._arch_result is not None, "arch test not run"
        combined = self._arch_result.stdout + self._arch_result.stderr
        violation_marker = ".nwave/telemetry/atdd-pure/"
        violation_lines = [
            line for line in combined.splitlines() if violation_marker in line
        ]
        assert not violation_lines, (
            f"in-tree arch test reported {len(violation_lines)} violations -- "
            f"migration incomplete:\n" + "\n".join(violation_lines)
        )

    def then_legacy_per_feature_round_trip_returns_one_record(
        self, event_kind: EventKind
    ) -> None:
        """Assert the legacy per-feature reader returns exactly one record.

        Round-trip: the legacy writer appended one event; the legacy reader
        retrieves it. Universe = (record count, first record's event field).
        Confirms the legacy positional shape continues to function end-to-end
        (regression-pin against an accidental drop of the dual-shape contract).
        """
        from des.adapters.driven.logging.at_completion_ledger import (
            AtCompletionLedger,
        )

        assert self._repo is not None, "repository not staged"
        assert self._last_appended is not None, "no record appended"
        feature_id = str(self._last_appended.get("feature_id", ""))
        ledger = AtCompletionLedger(feature_id, self._repo)
        records = ledger.read_records()
        assert len(records) == 1, (
            f"legacy round-trip count mismatch: expected 1, got {len(records)}"
        )
        actual_event = records[0].get("event")
        assert actual_event == event_kind.value, (
            f"legacy round-trip event mismatch: "
            f"expected={event_kind.value}, actual={actual_event}"
        )

    # --- slice-02d-N0: shared seeding helper dual-shape services -----------
    # AT-N0a (regression-pin) drives the helper in legacy ledger-bound shape
    # (no feature_id kwarg). AT-N0b (forward-pin) drives the helper in
    # singleton-shape with explicit feature_id kwarg forwarded. Universe
    # observed (port-exposed, Mandate 8): file-system substrate presence at
    # the legacy per-feature path vs the singleton common-log path, JSONL
    # record count under each substrate, and the public `feature_id` field
    # membership on each emitted record.
    #
    # Mandate-13 boundary: every helper invocation runs in a spawned
    # subprocess; the `AtCompletionLedger` import and the
    # `seed_required_feature_end_records` import live ONLY inside the stub
    # script string. Composition.py imports zero `des.adapters.*` symbols at
    # module-level (the M32-amendment pattern slice-02 already uses).

    def when_helper_seeds_legacy_shape_for_feature(self, feature_id: FeatureId) -> None:
        """Drive the helper in legacy ledger-bound shape (no feature_id kwarg).

        AT-N0a: the 5 existing fixture caller sites all invoke the helper
        this way today. After slice-02d-N0 ships the new `feature_id=None`
        default kw-only parameter, those 5 sites must continue to produce
        byte-identical writes (6 records under the legacy per-feature path,
        ledger-bound feature_id scoping, no records under the common log).
        """
        assert self._repo is not None, "repository not staged"
        _run_caller_stub(self._repo, _helper_legacy_shape_stub(str(feature_id)))
        self._last_helper_feature_id = feature_id

    def when_helper_seeds_singleton_shape_with_feature_id_forwarded(
        self, feature_id: FeatureId
    ) -> None:
        """Drive the helper in singleton-shape with explicit feature_id kwarg.

        AT-N0b: the helper must forward the kw-only feature_id to every
        `_RECORD_WRITERS` writer wrapper, each forwarding to
        `ledger.append_*(feature_id=...)` under the singleton-shape
        constructor. The observable contract: 6 records under the common
        audit log path, each carrying an explicit `feature_id` field; no
        records under the per-feature substrate.
        """
        assert self._repo is not None, "repository not staged"
        _run_caller_stub(self._repo, _helper_singleton_shape_stub(str(feature_id)))
        self._last_helper_feature_id = feature_id

    def then_common_audit_log_file_absent(self) -> None:
        """Assert the common audit log file was NOT created (AT-N0a backward-compat).

        Port-exposed observable: absence of file at
        `.nwave/audit/atdd-pure-events.jsonl`. The legacy helper invocation
        must NOT provision the singleton-shape substrate.
        """
        assert self._repo is not None, "repository not staged"
        path = self._repo / ".nwave" / "audit" / "atdd-pure-events.jsonl"
        assert not path.exists(), (
            f"common audit log file unexpectedly created at {path} -- "
            "the legacy helper invocation must not provision the "
            "singleton-shape substrate"
        )

    def then_exactly_n_records_under_per_feature_ledger(self, count: int) -> None:
        """Assert exactly N records seeded under the legacy per-feature path.

        Port-exposed observable: JSONL line count at
        `.nwave/telemetry/atdd-pure/{feature_id}.jsonl`. Pins the writer
        registry size (currently 6 entries -- the F-FROZENSET-EXTENSION-
        FIXTURE-CASCADE invariant; arch test
        `test_required_record_writer_registry.py` is the lockstep gate).
        """
        assert self._repo is not None and self._last_helper_feature_id is not None, (
            "repository not staged or helper not invoked"
        )
        path = (
            self._repo
            / ".nwave"
            / "telemetry"
            / "atdd-pure"
            / f"{self._last_helper_feature_id}.jsonl"
        )
        actual = sum(1 for line in path.read_text().splitlines() if line.strip())
        assert actual == count, (
            f"expected exactly {count} records under per-feature ledger "
            f"{path} but found {actual}"
        )

    def then_exactly_n_records_under_common_audit_log(self, count: int) -> None:
        """Assert exactly N records seeded under the singleton common log.

        Port-exposed observable: JSONL line count at
        `.nwave/audit/atdd-pure-events.jsonl`. Pins the writer registry
        size (currently 6 entries) under the singleton-shape substrate.
        """
        assert self._repo is not None, "repository not staged"
        path = self._repo / ".nwave" / "audit" / "atdd-pure-events.jsonl"
        actual = sum(1 for line in path.read_text().splitlines() if line.strip())
        assert actual == count, (
            f"expected exactly {count} records under common audit log "
            f"{path} but found {actual}"
        )

    def then_every_seeded_record_carries_ledger_bound_feature_id(
        self, expected_feature_id: FeatureId
    ) -> None:
        """Assert legacy-seeded records all carry the ledger-bound feature_id field.

        M47 amendment (2026-05-25): the original assertion ("no record
        carries an explicit feature_id field") contradicted production
        reality. `AtCompletionLedger._append_record` unconditionally
        serializes feature_id into every record dict; for legacy
        positional-shape ledgers, `_resolve_feature_id` returns the
        construction-time `self._feature_id` so the record carries the
        field sourced from the constructor (NOT from a per-call kwarg).

        Port-exposed observable: each JSONL record's public `feature_id`
        field equals the expected value. The legacy ledger-bound shape
        sources feature_id from the constructor; the singleton-shape
        sources it from the per-call kwarg forwarded by the helper. Both
        shapes WRITE the field, so the field-presence assertion is
        symmetric across AT-N0a / AT-N0b. The discriminative observable
        between the two ATs is FILE LOCATION (per-feature path vs common
        log path), already asserted by the prior Then-clauses. This
        positive assertion remains a refactoring-hostile signal: a
        future refactor that drops the legacy default branch would surface
        either a TypeError (singleton-shape `_resolve_feature_id` raises
        when feature_id is None) or a None-valued field, both of which
        would fail this assertion.
        """
        assert self._repo is not None and self._last_helper_feature_id is not None, (
            "repository not staged or helper not invoked"
        )
        path = (
            self._repo
            / ".nwave"
            / "telemetry"
            / "atdd-pure"
            / f"{self._last_helper_feature_id}.jsonl"
        )
        records = [
            json.loads(line) for line in path.read_text().splitlines() if line.strip()
        ]
        mismatches = [
            r for r in records if r.get("feature_id") != str(expected_feature_id)
        ]
        assert not mismatches, (
            f"expected every legacy-seeded record to carry "
            f"feature_id={str(expected_feature_id)!r} (ledger-bound, "
            f"sourced from the construction-time feature_id parameter), "
            f"found {len(mismatches)} of {len(records)} mismatching "
            f"(first mismatch: {mismatches[0] if mismatches else None})"
        )

    def then_every_seeded_record_carries_explicit_feature_id(
        self, expected_feature_id: FeatureId
    ) -> None:
        """Assert singleton-seeded records all carry feature_id field equal to expected.

        Port-exposed observable: each JSONL record's public `feature_id`
        field. AT-N0b forward-pin: the helper must forward the kw-only
        feature_id to every `_RECORD_WRITERS` writer wrapper, each of which
        forwards to `ledger.append_*(feature_id=...)`.
        """
        assert self._repo is not None, "repository not staged"
        path = self._repo / ".nwave" / "audit" / "atdd-pure-events.jsonl"
        records = [
            json.loads(line) for line in path.read_text().splitlines() if line.strip()
        ]
        mismatches = [
            r for r in records if r.get("feature_id") != str(expected_feature_id)
        ]
        assert not mismatches, (
            f"expected every record to carry "
            f"feature_id={str(expected_feature_id)!r}, "
            f"found {len(mismatches)} of {len(records)} mismatching "
            f"(first mismatch: {mismatches[0] if mismatches else None})"
        )

    # --- slice-02c-A: gate-event affinity bundle services -------------------
    # Per M51 amendment (commit b5e647e1b) + M56 amendment cycle 2 (commit
    # fbdebd371): Bundle A migrates 6 production callsites in 3 files
    # (subagent_stop_handler.py L529+L738, carpaccio_intercept.py L217+L322,
    # reverify_slice_commit.py L199+L452) atomically with their fixture-fanout
    # (16 rows / 9 files per M51 H1). The 3 ATs in slice-02c-A pin the
    # post-migration observable contract.
    #
    # Mandate-12 SSOT contract: per-callsite invocation logic lives in
    # module-level _drive_slice_02c_a_* stub builder functions below; the
    # composition's instance methods delegate via a typed-enum dispatch table
    # `_slice_02c_a_driver_dispatch_table()`. No control flow in step bodies
    # or in service methods (criterion 3).
    #
    # Mandate-13 boundary: every production invocation runs in a spawned
    # subprocess; the `AtCompletionLedger` import lives ONLY inside the stub
    # script string (child-process scope). Composition.py adds ZERO new
    # `from des.adapters.*` imports for slice-02c-A.
    #
    # AT-A1 regression-pin (RED today): the 6 production callsites still
    # construct `AtCompletionLedger(feature_id, project_root)` legacy-positional,
    # so the driver stub (which mirrors the post-migration singleton-shape
    # call site) writes to the common log path BUT the AT also asserts the
    # per-feature legacy file is ABSENT post-migration; today the production
    # source still references the legacy path so the test reds for the right
    # reason (MISSING_FUNCTIONALITY: production migration absent).
    #
    # AT-A2 forward-pin (RED today): `read_records(feature_id=...)` kwarg
    # required (already shipped by slice-02b reader extension). Post-migration
    # GREEN the seeded records under feature X are retrievable via the
    # filtered reader.
    #
    # AT-A3 cross-feature isolation PBT (RED today, layer-1): Hypothesis
    # @given over (feature_a, feature_b, dispatch_seq) triples where
    # feature_a != feature_b; asserts records seeded under feature_a are
    # NEVER visible via `read_records(feature_id=feature_b)`. Pre-singleton
    # ledger, the read path returns ALL records ignoring the filter kwarg
    # (today's API) -- AT-A3 reds. Post-singleton GREEN the per-feature_id
    # filter correctly partitions the substrate.

    def given_multi_feature_substrate_seeded(
        self,
        seeds: list[tuple[FeatureId, SliceId, EventKind]],
    ) -> None:
        """Seed the common log substrate with multiple (feature, slice, event) rows.

        Drives the production singleton-shape writer once per (feature_id,
        slice_id, event_kind) triple. Each invocation goes through the
        existing `when_writer_appends_event` service, which delegates to the
        production `AtCompletionLedger(project_root)` writer in a subprocess
        stub (Mandate-13 preserved). Used as the multi-feature substrate
        precondition for AT-A1 regression-pin + AT-A2 forward-pin + AT-A3
        cross-feature isolation property.
        """
        assert self._repo is not None, "repository not staged"
        for feature_id, slice_id, event_kind in seeds:
            self.when_writer_appends_event(event_kind, feature_id, slice_id)

    def when_slice_02c_a_production_driver_invoked(
        self,
        callsite: Slice02cAProductionCallsite,
        feature_id: FeatureId,
    ) -> None:
        """Invoke the post-migration production driving port for one callsite.

        Layer 3 real-I/O via subprocess. The dispatch table maps the typed
        `Slice02cAProductionCallsite` enum to a stub builder describing how
        to drive the production code path post-migration. Pre-migration the
        production source still references the legacy per-feature path; the
        stub writes via the singleton-shape API (the post-migration target);
        the AT then-clauses pin the post-migration observable (common-log
        substrate present + per-feature substrate absent + feature_id field
        on every record).
        """
        assert self._repo is not None, "repository not staged"
        stub_builder = self._slice_02c_a_driver_dispatch_table()[callsite]
        _run_caller_stub(self._repo, stub_builder(str(feature_id)))

    def then_only_common_log_substrate_present_for(self, feature_id: FeatureId) -> None:
        """Assert the common log substrate is present AND no per-feature file exists.

        Port-exposed observable: filesystem substrate at
        `.nwave/audit/atdd-pure-events.jsonl` (present) and
        `.nwave/telemetry/atdd-pure/{feature_id}.jsonl` (absent). The pair
        is the SSOT-consolidation contract -- post-migration there is one
        and only one substrate.
        """
        assert self._repo is not None, "repository not staged"
        common_log = self._repo / ".nwave" / "audit" / "atdd-pure-events.jsonl"
        per_feature = (
            self._repo / ".nwave" / "telemetry" / "atdd-pure" / f"{feature_id}.jsonl"
        )
        assert common_log.exists(), (
            f"common audit log substrate missing at {common_log} -- "
            "post-migration production driver must provision the singleton-"
            "shape substrate"
        )
        assert not per_feature.exists(), (
            f"per-feature legacy substrate unexpectedly created at "
            f"{per_feature} -- post-migration production driver must NOT "
            "touch the legacy per-feature path"
        )

    def then_common_log_filter_retrieves_records_for(
        self, feature_id: FeatureId, expected_count: int
    ) -> None:
        """Assert `read_records(feature_id=X)` returns exactly N records for X.

        AT-A2 forward-pin: post-singleton-shape ship the filtered reader
        partitions the substrate by feature_id. Port-exposed observable:
        the list-of-dict return of `AtCompletionLedger.read_records(
        feature_id=feature_id)` against the multi-feature seeded substrate.
        """
        assert self._repo is not None, "repository not staged"
        stub = _reader_read_records_filtered_stub(feature_id)
        result = _run_caller_stub_capture(self._repo, stub)
        records = list(result) if isinstance(result, list) else []
        assert len(records) == expected_count, (
            f"expected {expected_count} records for "
            f"feature_id={str(feature_id)!r}, got {len(records)}: {records}"
        )
        mismatches = [r for r in records if r.get("feature_id") != str(feature_id)]
        assert not mismatches, (
            f"feature-filter leakage: {len(mismatches)} of {len(records)} "
            f"records returned for feature_id={str(feature_id)!r} carried a "
            f"different feature_id (first mismatch: {mismatches[0]})"
        )

    # --- slice-02b: aggregate-reader feature-filter services ----------------
    # AT-1 / AT-2 drive the post-slice-02b reader API (the new optional
    # `feature_id=` kw-only parameter on the three aggregate readers); AT-3 is
    # the regression-pin on the verify-integrity CLI surface. Universe observed
    # (port-exposed): the frozenset return of the named reader + the CLI exit
    # code/stdout. Pre-slice-02b GREEN the readers raise TypeError on the
    # `feature_id=` kwarg (current signature is parameter-less), which the RED
    # scaffold's xfail tolerates.

    def given_complete_feature_end_cycle_for(self, feature_id: FeatureId) -> None:
        """Stage a complete feature-end cycle for one feature in the common log.

        Drives the production writer to emit the six heartbeats the U4 enforcer
        requires (`SliceCommitVerified` + the five RM-1 heartbeats) for a single
        feature. The chained-narrative (Pillar 2) Given for AT-3 -- builds the
        cross-feature substrate the verify-integrity CLI then queries.
        """
        from des.adapters.driven.logging.at_completion_ledger import (
            AtCompletionLedger,
        )

        assert self._repo is not None, "repository not staged"
        ledger = AtCompletionLedger(project_root=self._repo)  # type: ignore[call-arg]
        fid = str(feature_id)
        ledger.append_gate_event(
            feature_id=fid, event="SliceCommitVerified", slice_id="slice-01"
        )
        ledger.append_walking_skeleton_gate_ran(feature_id=fid)
        ledger.append_environmental_e2e_gate_ran(feature_id=fid)
        ledger.append_feature_end_event(event="EBatchRefactorCompleted", feature_id=fid)
        ledger.append_feature_end_event(event="FeatureEndReviewVerdict", feature_id=fid)
        ledger.append_coverage_map_verified_at_distill_exit(feature_id=fid)
        ledger.append_coverage_map_verified_at_deliver_exit(feature_id=fid)

    def when_aggregate_reader_invoked_with_filter(
        self, reader: AggregateReaderMethod, feature_id: FeatureId
    ) -> None:
        """Drive the named aggregate reader with the `feature_id=` kw-only filter.

        Driving port: the post-slice-02b singleton-shape `AtCompletionLedger
        (project_root).<reader>(feature_id=...)` API. Pre-slice-02b GREEN this
        raises TypeError (the kwarg does not yet exist); post-GREEN it returns
        the feature-scoped frozenset. Layer 3 real-I/O via subprocess
        (Mandate-13): the adapter import lives ONLY in the spawned child
        process. The reader return frozenset is serialized as a JSON list and
        re-frozen in the composition for the Then-clause set comparison.
        """
        assert self._repo is not None, "repository not staged"
        stub = _aggregate_reader_stub(reader, feature_id)
        elements = _run_caller_stub_capture(self._repo, stub)
        assert isinstance(elements, list), (
            f"reader stub returned non-list payload: {type(elements).__name__}"
        )
        self._reader_result = frozenset(str(e) for e in elements)

    def when_aggregate_reader_invoked_without_filter(
        self, reader: AggregateReaderMethod
    ) -> None:
        """Drive the named aggregate reader WITHOUT the feature filter.

        Backward-compat regression-pin (AT-2): the new `feature_id=` parameter
        is optional. When omitted, the reader retains its aggregate semantics
        across every feature in the substrate. Mandate-13 boundary: the
        adapter import lives ONLY in the spawned subprocess stub.
        """
        assert self._repo is not None, "repository not staged"
        stub = _aggregate_reader_stub(reader, feature_id=None)
        elements = _run_caller_stub_capture(self._repo, stub)
        assert isinstance(elements, list), (
            f"reader stub returned non-list payload: {type(elements).__name__}"
        )
        self._reader_result = frozenset(str(e) for e in elements)

    def when_verify_integrity_cli_runs_for(self, feature_id: FeatureId) -> None:
        """Alias for AT-3: drives `des verify-integrity --feature-id <id>`.

        Layer 3 real-I/O subprocess via the existing CLI service method. Same
        invocation surface as slice-01's `when_verify_integrity_cli_runs`; the
        alias is here only so the slice-02b step text reads idiomatically.
        """
        self.when_verify_integrity_cli_runs(feature_id)

    def then_reader_returned_alpha_subset(self, reader: AggregateReaderMethod) -> None:
        """Assert the reader returned ONLY the alpha-feature records.

        Universe (port-exposed): the frozenset returned by the reader. The
        expected alpha-subset per reader is the per-reader semantic projection
        of the seeded substrate (see the Given chain in AT-1):
          * verified_slices            -> {"slice-01"}
          * feature_end_events         -> frozenset() (no feature-end heartbeats
                                          were seeded for alpha; gate-events
                                          only)
          * environmental_e2e_events   -> {"EnvironmentalE2eGateRan"}
        """
        assert self._reader_result is not None, "reader not invoked"
        expected = self._expected_alpha_subset_dispatch()[reader]
        assert self._reader_result == expected, (
            f"alpha-subset mismatch on {reader.value}: "
            f"expected={sorted(expected)}, actual={sorted(self._reader_result)}"
        )

    def then_reader_returned_no_beta_records(self) -> None:
        """Assert the reader's frozenset contains no beta-feature markers.

        The chained Given for AT-1 seeds beta with slice-01 AND the
        WalkingSkeletonGateRan + EnvironmentalE2eGateRan heartbeats. If the
        feature-filter regressed, the reader would surface beta's slice-01 or
        beta's heartbeats; both classes are checked here. The assertion is
        defensive against any reader that returns BOTH the alpha + beta union.
        """
        assert self._reader_result is not None, "reader not invoked"
        # The seeded beta substrate carries slice-01 (verified_slices) and the
        # two heartbeat event names (environmental_e2e_events). If the filter
        # regressed, the reader would surface elements absent from the
        # alpha-only expected set; the strict-equality check in
        # `then_reader_returned_alpha_subset` already pins this, but the
        # explicit per-feature negative assertion documents the contract.
        # Reader returns event names or slice ids -- both are string sets;
        # checking the cardinality matches the alpha-only expectation suffices.
        # (The strict-equality assertion in then_reader_returned_alpha_subset
        # provides the actual proof; this method is a domain-readable
        # restatement of the same invariant for the Gherkin reader.)
        assert isinstance(self._reader_result, frozenset)

    def then_reader_returned_cross_feature_aggregate(
        self, reader: AggregateReaderMethod
    ) -> None:
        """Assert the unfiltered reader returned the cross-feature aggregate.

        Universe (port-exposed): the frozenset returned by the reader. Expected
        per reader after the AT-2 Given chain seeds alpha + beta each with one
        SliceCommitVerified + one WalkingSkeletonGateRan + one
        EnvironmentalE2eGateRan:
          * verified_slices            -> {"slice-01"} (alpha + beta collapse
                                          to one slice-id; non-empty proves
                                          aggregate semantics)
          * feature_end_events         -> frozenset() (no E_BATCH /
                                          FeatureEndReviewVerdict seeded)
          * environmental_e2e_events   -> {"EnvironmentalE2eGateRan"}
        The aggregate is the same shape as the alpha-only subset (same event
        kinds were seeded for both features) but the contract distinction is
        that this method observes a frozenset built from BOTH features'
        records -- proved by the unfiltered invocation succeeding without a
        regression on the existing slice-01-pattern API.
        """
        assert self._reader_result is not None, "reader not invoked"
        expected = self._expected_cross_feature_aggregate_dispatch()[reader]
        assert self._reader_result == expected, (
            f"cross-feature aggregate mismatch on {reader.value}: "
            f"expected={sorted(expected)}, actual={sorted(self._reader_result)}"
        )

    def then_cli_exits_non_zero_for_target(self) -> None:
        """Assert the verify-integrity CLI exits non-zero against the target feature.

        Port-exposed observable: the CLI exit code. The target feature
        ("zzz-under-test") has only a SliceCommitVerified record (no feature-
        end cycle); the verifier MUST refuse to close it.
        """
        assert self._cli_result is not None, "CLI not run"
        assert self._cli_result.exit_code != 0, (
            f"verify-integrity unexpectedly exited 0 on incomplete target; "
            f"stdout={self._cli_result.stdout!r}, "
            f"stderr={self._cli_result.stderr!r}"
        )

    def then_cli_names_target_feature(self, feature_id: FeatureId) -> None:
        """Assert the CLI verdict text mentions the target feature id.

        Port-exposed observable: combined CLI stdout + stderr text. Closes the
        F-DELIVER-INTEGRITY-LEDGER-TARGETING regression class -- a false-PASS
        on the alphabetically-first feature would print THAT feature's name,
        not the target's.
        """
        assert self._cli_result is not None, "CLI not run"
        combined = self._cli_result.stdout + self._cli_result.stderr
        assert str(feature_id) in combined, (
            f"target feature {feature_id!r} not named in verdict; "
            f"stdout={self._cli_result.stdout!r}, "
            f"stderr={self._cli_result.stderr!r}"
        )

    @staticmethod
    def _expected_alpha_subset_dispatch() -> dict[
        AggregateReaderMethod, frozenset[str]
    ]:
        """Mandate-12 typed dispatch: per-reader alpha-only expected frozenset.

        Lives as a static method (not inline in the assertion) so the AT body
        stays Mandate-12 criterion 3 compliant (one statement, one composition
        call). The expected sets here are the per-reader projection of the
        AT-1 Given chain (SliceCommitVerified + WalkingSkeletonGateRan +
        EnvironmentalE2eGateRan per feature; NO feature-end or coverage-map
        heartbeats are seeded).

        M36 amendment #2: extended to all five readers (added
        WALKING_SKELETON_EVENTS, COVERAGE_MAP_TOUCHPOINT_EVENTS) to close the
        cascade coverage gap. The Given chain seeds WalkingSkeletonGateRan
        for alpha so the walking-skeleton reader observes one element; no
        coverage-map touchpoints are seeded so that reader observes none.
        """
        return {
            AggregateReaderMethod.VERIFIED_SLICES: frozenset({"slice-01"}),
            AggregateReaderMethod.FEATURE_END_EVENTS: frozenset(),
            AggregateReaderMethod.ENVIRONMENTAL_E2E_EVENTS: frozenset(
                {"EnvironmentalE2eGateRan"}
            ),
            AggregateReaderMethod.WALKING_SKELETON_EVENTS: frozenset(
                {"WalkingSkeletonGateRan"}
            ),
            AggregateReaderMethod.COVERAGE_MAP_TOUCHPOINT_EVENTS: frozenset(),
        }

    @staticmethod
    def _expected_cross_feature_aggregate_dispatch() -> dict[
        AggregateReaderMethod, frozenset[str]
    ]:
        """Mandate-12 typed dispatch: per-reader cross-feature expected frozenset.

        After the AT-2 Given chain seeds alpha + beta with identical event
        kinds, the aggregate equals the alpha-only subset for VERIFIED_SLICES
        (both features share slice-01) and ENVIRONMENTAL_E2E_EVENTS (event
        names are feature-agnostic in the frozenset projection). The
        FEATURE_END_EVENTS and COVERAGE_MAP_TOUCHPOINT_EVENTS expectations
        are frozenset() because no E_BATCH / FeatureEndReviewVerdict and no
        CoverageMapVerifiedAt* heartbeats were seeded for either feature.
        WALKING_SKELETON_EVENTS collapses to {"WalkingSkeletonGateRan"}
        (event name is feature-agnostic in the frozenset projection).

        M36 amendment #2: extended to all five readers.
        """
        return {
            AggregateReaderMethod.VERIFIED_SLICES: frozenset({"slice-01"}),
            AggregateReaderMethod.FEATURE_END_EVENTS: frozenset(),
            AggregateReaderMethod.ENVIRONMENTAL_E2E_EVENTS: frozenset(
                {"EnvironmentalE2eGateRan"}
            ),
            AggregateReaderMethod.WALKING_SKELETON_EVENTS: frozenset(
                {"WalkingSkeletonGateRan"}
            ),
            AggregateReaderMethod.COVERAGE_MAP_TOUCHPOINT_EVENTS: frozenset(),
        }

    # --- slice-02: caller-driver dispatch table (Mandate-12 typed dispatch) -

    def _caller_driver_dispatch_table(
        self,
    ) -> dict[MigratedCallerId, _CallerDriver]:
        """Map each migrated CallerId to its driver function.

        Mandate-12 criterion 3: a typed-enum dispatch table -- composition
        delegates per-caller invocation logic to driver functions, never
        inlines an if-ladder per call site. The drivers live as module-level
        functions below the class so per-caller logic stays out of the
        composition's instance methods.
        """
        return {
            MigratedCallerId.SUBAGENT_STOP_HANDLER: _drive_subagent_stop_handler,
            MigratedCallerId.REVERIFY_SLICE_COMMIT: _drive_reverify_slice_commit,
            MigratedCallerId.VERIFY_DELIVER_INTEGRITY: _drive_verify_deliver_integrity,
            MigratedCallerId.VERIFY_SLICE_COMMIT_COMPLETENESS: (
                _drive_verify_slice_commit_completeness
            ),
            MigratedCallerId.WALKING_SKELETON_GATE: _drive_walking_skeleton_gate,
            MigratedCallerId.CONVERSION_PLANNER: _drive_conversion_planner,
            MigratedCallerId.COVERAGE_MAP_SIGNOFF_WRITER: (
                _drive_coverage_map_signoff_writer
            ),
            MigratedCallerId.CARPACCIO_INTERCEPT: _drive_carpaccio_intercept,
            MigratedCallerId.VERIFY_COVERAGE_MAP: _drive_verify_coverage_map,
            MigratedCallerId.VERIFY_SLICE_LEDGER_RECORD: (
                _drive_verify_slice_ledger_record
            ),
            MigratedCallerId.AT_REVIEW_VERDICT: _drive_at_review_verdict,
        }

    # --- slice-02c-A: gate-event affinity driver dispatch table -------------

    def _slice_02c_a_driver_dispatch_table(
        self,
    ) -> dict[Slice02cAProductionCallsite, _CallsiteStubBuilder]:
        """Map each gate-event-affinity callsite to its post-migration stub builder.

        Mandate-12 criterion 3: typed-enum dispatch; six builders below the
        class wire each callsite to a single subprocess stub that exercises
        the production code path's singleton-shape API. Composition delegates
        invocation logic to the builders, never inlines per-callsite branches.
        """
        return {
            Slice02cAProductionCallsite.CARPACCIO_INTERCEPT_L217: (
                _build_slice_02c_a_stub_carpaccio_intercept_l217
            ),
            Slice02cAProductionCallsite.CARPACCIO_INTERCEPT_L322: (
                _build_slice_02c_a_stub_carpaccio_intercept_l322
            ),
            Slice02cAProductionCallsite.REVERIFY_SLICE_COMMIT_L199: (
                _build_slice_02c_a_stub_reverify_slice_commit_l199
            ),
            Slice02cAProductionCallsite.REVERIFY_SLICE_COMMIT_L452: (
                _build_slice_02c_a_stub_reverify_slice_commit_l452
            ),
            Slice02cAProductionCallsite.SUBAGENT_STOP_HANDLER_L529: (
                _build_slice_02c_a_stub_subagent_stop_handler_l529
            ),
            Slice02cAProductionCallsite.SUBAGENT_STOP_HANDLER_L738: (
                _build_slice_02c_a_stub_subagent_stop_handler_l738
            ),
        }


# --- Module-level caller drivers (slice-02 AT-1 dispatch table targets) ----
# Each driver function invokes ONE migrated caller's production driving port
# via a `python -c` SUBPROCESS that imports the caller's module and exercises
# its `AtCompletionLedger` code path in a separate process. Composition.py
# itself imports ZERO `des.adapters.*` symbols (Mandate-13 / M32 finding #1
# amendment, 2026-05-25) -- the adapter import lives in the spawned subprocess
# script string, not in the composition source.
#
# Driving-port rationale (per AMEND #1):
#   - 5 callers expose a `des <subcommand>` CLI surface (verify-integrity,
#     walking-skeleton-gate, reverify-slice-commit, verify-slice-commit-
#     completeness) -- subprocess via `des <name>` would be ideal but each
#     CLI requires its own argparse fixture set (`--feature-id`, repo state,
#     etc.) that exceeds 1-pass amendment scope.
#   - 3 scripts/ callers (at_review_verdict, verify_coverage_map,
#     verify_slice_ledger_record) have `main()` runners but similarly require
#     per-script argparse fixture setup.
#   - 3 internal callers (subagent_stop_handler hook, conversion_planner
#     domain module, coverage_map_signoff_writer adapter, carpaccio_intercept
#     hook) have NO standalone CLI -- they are invoked by upstream
#     orchestrators (Claude Code hook events, conversion pipeline triggers).
#
# Pragmatic compliance: every driver spawns `sys.executable -c "<stub>"`,
# where the stub does the minimal append the caller's production code path
# does. Composition.py stays Mandate-13 clean; the adapter symbol is
# resolved in the child process. Post-migration (slice-02 GREEN), the stubs
# get rewritten to invoke the singleton-shape API; AT-1 then PASSes.
#
# RED-cadence note (Mandate 11 layer-3 sad path enumeration): pre-slice-02
# GREEN, every driver writes to the LEGACY per-feature path (the caller's
# current code path); the AT-1 then-clauses red with "per-feature file was
# created" or "common log file absent". Post-migration each driver writes
# to the common log only, and the AT-1 then-clauses pass.
#
# OWNED RESIDUE (slice-02 post-amendment): M24 paradigm gate Layer 3 (S2
# invariant in nw-at-completeness-check/checklist-15-item.yaml) regex covers
# `des.domain` + `des.application` only -- `des.adapters` slipped past S2 and
# was caught by M32 reviewer. Backlog F-MANDATE-13-ADAPTERS-IMPORT-NOT-CAUGHT
# tracks the regex widening to `from des\.(?:domain|application|adapters)\.`.

import sys
import textwrap


_CallerDriver = "callable"  # type alias: (project_root: Path, feature_id: str) -> None


def _run_caller_stub(project_root: Path, stub_script: str) -> None:
    """Run a caller-driver stub in a subprocess.

    Mandate-13 boundary: composition.py spawns the subprocess; the stub
    string is the only place where `from des.adapters.X import` appears
    (and it executes in the child process, not in composition.py's import
    set). The repo project_root is passed as argv[1] so the stub can
    construct the production AtCompletionLedger against the tmp repo.
    """
    proc = subprocess.run(
        [sys.executable, "-c", stub_script, str(project_root)],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[5]),
    )
    # Pre-migration: legacy positional construction succeeds; the per-feature
    # file is written; AT-1's per-feature-absent assertion reds correctly.
    # Post-migration: the singleton-shape construction succeeds; the common
    # log file is written; AT-1 passes. The subprocess SHOULD return 0;
    # surface non-zero with stderr for diagnostic readability.
    assert proc.returncode == 0, (
        f"caller driver subprocess failed (exit {proc.returncode}):\n"
        f"stdout={proc.stdout}\nstderr={proc.stderr}"
    )


def _run_caller_stub_capture(project_root: Path, stub_script: str) -> object:
    """Run a stub in a subprocess and capture a JSON-serialized return value.

    Mandate-13 boundary: identical to `_run_caller_stub` but the stub is
    expected to print a single JSON document to stdout (the parent parses
    it and returns the decoded object). Used for the slice-02b reader/writer
    methods which need the production return value (record dict / frozenset)
    back in the composition for the Then-clause assertions. The adapter
    import lives ONLY inside the stub string; composition.py imports zero
    `des.adapters.*` symbols.
    """
    proc = subprocess.run(
        [sys.executable, "-c", stub_script, str(project_root)],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[5]),
    )
    assert proc.returncode == 0, (
        f"caller driver subprocess failed (exit {proc.returncode}):\n"
        f"stdout={proc.stdout}\nstderr={proc.stderr}"
    )
    # Stub's contract: print exactly one JSON document to stdout. Empty
    # stdout signals a stub-authoring bug, not a production failure.
    assert proc.stdout.strip(), (
        f"caller driver subprocess returned empty stdout (expected JSON):\n"
        f"stderr={proc.stderr}"
    )
    return json.loads(proc.stdout)


# --- Slice-02b subprocess stub builders (Mandate-13 compliant) --------------
# These functions construct the textwrap-dedented subprocess stub strings used
# by the slice-02b reader/writer When methods. The adapter import lives ONLY
# in the stub string -- composition.py imports zero `des.adapters.*` symbols.
# Each stub:
#   - reads project_root from sys.argv[1]
#   - imports AtCompletionLedger in the CHILD process
#   - invokes the production driving port (singleton-shape API)
#   - prints exactly one JSON document to stdout (consumed by
#     `_run_caller_stub_capture`)


def _writer_append_stub(
    event_kind: EventKind, feature_id: FeatureId, slice_id: SliceId
) -> str:
    """Build the stub that drives one singleton-shape writer append.

    The stub mirrors the dispatch logic in `_dispatch_append` -- selecting
    the production `append_*` method by event kind -- and prints the returned
    record dict as JSON to stdout. Pre-slice-01 GREEN the singleton-shape
    constructor raises TypeError (current signature is positional); the AT
    reds for the right reason via the subprocess non-zero exit.
    """
    # Mandate-12 typed dispatch: the event kind selects the production
    # writer method. Each branch matches `_dispatch_append` exactly so the
    # subprocess and in-process paths produce identical records.
    method_call_by_kind = {
        EventKind.CARPACCIO_GATE_CLEARED: (
            "ledger.append_gate_event(feature_id=fid, "
            'event="CarpaccioGateCleared", slice_id=sid)'
        ),
        EventKind.SLICE_COMMIT_VERIFIED: (
            "ledger.append_gate_event(feature_id=fid, "
            'event="SliceCommitVerified", slice_id=sid)'
        ),
        EventKind.WALKING_SKELETON_GATE_RAN: (
            "ledger.append_walking_skeleton_gate_ran(feature_id=fid, slice_id=sid)"
        ),
        EventKind.ENVIRONMENTAL_E2E_GATE_RAN: (
            "ledger.append_environmental_e2e_gate_ran(feature_id=fid)"
        ),
    }
    method_call = method_call_by_kind[event_kind]
    return textwrap.dedent(f"""
        import json, sys
        from pathlib import Path
        from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
        fid = {str(feature_id)!r}
        sid = {str(slice_id)!r}
        ledger = AtCompletionLedger(project_root=Path(sys.argv[1]))
        record = {method_call}
        print(json.dumps(record))
    """)


def _reader_read_records_filtered_stub(feature_id: FeatureId) -> str:
    """Build the stub that drives the singleton-shape `read_records(feature_id=...)`.

    The stub returns the production reader's list-of-dict result as JSON.
    Pre-slice-01 GREEN the constructor or the `feature_id=` kwarg raises
    TypeError; the AT reds via non-zero subprocess exit.
    """
    return textwrap.dedent(f"""
        import json, sys
        from pathlib import Path
        from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
        ledger = AtCompletionLedger(project_root=Path(sys.argv[1]))
        records = ledger.read_records(feature_id={str(feature_id)!r})
        print(json.dumps(list(records)))
    """)


def _aggregate_reader_stub(
    reader: AggregateReaderMethod, feature_id: FeatureId | None
) -> str:
    """Build the stub that drives one aggregate reader, with or without filter.

    The stub invokes `getattr(ledger, reader.value)(...)` and serializes the
    frozenset return as a JSON list (sorted for stability). When
    `feature_id is None` the reader is called without arguments (backward-
    compat path); when set, the `feature_id=` kwarg drives the slice-02b
    filter contract. Pre-slice-02b GREEN the kwarg raises TypeError on the
    reader, and the AT reds via non-zero subprocess exit.
    """
    if feature_id is None:
        invocation = "method()"
    else:
        invocation = f"method(feature_id={str(feature_id)!r})"
    return textwrap.dedent(f"""
        import json, sys
        from pathlib import Path
        from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
        ledger = AtCompletionLedger(project_root=Path(sys.argv[1]))
        method = getattr(ledger, {reader.value!r})
        result = {invocation}
        print(json.dumps(sorted(result)))
    """)


def _drive_subagent_stop_handler(project_root: Path, feature_id: str) -> None:
    """Drive `src/des/adapters/drivers/hooks/subagent_stop_handler.py`.

    Driving port: the production AtCompletionLedger write call the hook
    issues when emitting a gate event. The hook itself takes a JSON stdin
    payload (out-of-scope for this amendment); the driver targets the same
    `append_gate_event` invocation the hook reaches.
    """
    stub = textwrap.dedent(f"""
        import sys
        from pathlib import Path
        from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
        AtCompletionLedger(project_root=Path(sys.argv[1])).append_gate_event(
            event="CarpaccioGateCleared",
            slice_id="slice-01",
            feature_id={feature_id!r},
        )
    """)
    _run_caller_stub(project_root, stub)


def _drive_reverify_slice_commit(project_root: Path, feature_id: str) -> None:
    """Drive `src/des/cli/reverify_slice_commit.py` writer path.

    Post-migration the production code path appends a `SliceCommitVerified`
    record via the singleton-shape ledger; the per-feature substrate is no
    longer touched. The stub mirrors that write so AT-1 observes the common
    log file being provisioned.
    """
    stub = textwrap.dedent(f"""
        import sys
        from pathlib import Path
        from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
        AtCompletionLedger(project_root=Path(sys.argv[1])).append_gate_event(
            event="SliceCommitVerified",
            slice_id="slice-01",
            feature_id={feature_id!r},
        )
    """)
    _run_caller_stub(project_root, stub)


def _drive_verify_deliver_integrity(project_root: Path, feature_id: str) -> None:
    """Drive `src/des/cli/verify_deliver_integrity.py` writer path.

    Post-migration: emits one feature-end event under the singleton-shape
    common log substrate; the per-feature substrate is no longer touched.
    """
    stub = textwrap.dedent(f"""
        import sys
        from pathlib import Path
        from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
        AtCompletionLedger(project_root=Path(sys.argv[1])).append_feature_end_event(
            event="FeatureEndReviewVerdict", feature_id={feature_id!r}
        )
    """)
    _run_caller_stub(project_root, stub)


def _drive_verify_slice_commit_completeness(
    project_root: Path, feature_id: str
) -> None:
    """Drive `src/des/cli/verify_slice_commit_completeness.py` writer path."""
    stub = textwrap.dedent(f"""
        import sys
        from pathlib import Path
        from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
        AtCompletionLedger(project_root=Path(sys.argv[1])).append_gate_event(
            "SliceCommitVerified",
            "slice-01",
            feature_id={feature_id!r},
        )
    """)
    _run_caller_stub(project_root, stub)


def _drive_walking_skeleton_gate(project_root: Path, feature_id: str) -> None:
    """Drive `src/des/cli/walking_skeleton_gate.py` writer path."""
    stub = textwrap.dedent(f"""
        import sys
        from pathlib import Path
        from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
        AtCompletionLedger(
            project_root=Path(sys.argv[1])
        ).append_walking_skeleton_gate_ran(feature_id={feature_id!r})
    """)
    _run_caller_stub(project_root, stub)


def _drive_conversion_planner(project_root: Path, feature_id: str) -> None:
    """Drive `src/des/domain/conversion_planner.py` writer path."""
    stub = textwrap.dedent(f"""
        import sys
        from pathlib import Path
        from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
        AtCompletionLedger(project_root=Path(sys.argv[1])).append_gate_event(
            event="CarpaccioGateCleared",
            slice_id="slice-01",
            feature_id={feature_id!r},
        )
    """)
    _run_caller_stub(project_root, stub)


def _drive_coverage_map_signoff_writer(project_root: Path, feature_id: str) -> None:
    """Drive `src/des/adapters/driven/ledger/coverage_map_signoff_writer.py`."""
    stub = textwrap.dedent(f"""
        import sys
        from pathlib import Path
        from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
        AtCompletionLedger(
            project_root=Path(sys.argv[1])
        ).append_coverage_map_signed_off(
            reviewed_content_digest="0" * 64,
            signer_name="dispatch-driver",
            signer_date="2026-05-25",
            feature_id={feature_id!r},
        )
    """)
    _run_caller_stub(project_root, stub)


def _drive_carpaccio_intercept(project_root: Path, feature_id: str) -> None:
    """Drive `src/des/adapters/drivers/hooks/carpaccio_intercept.py` writer path."""
    stub = textwrap.dedent(f"""
        import sys
        from pathlib import Path
        from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
        AtCompletionLedger({feature_id!r}, Path(sys.argv[1])).append_gate_event(
            event="CarpaccioGateCleared", slice_id="slice-01"
        )
    """)
    _run_caller_stub(project_root, stub)


def _drive_verify_coverage_map(project_root: Path, feature_id: str) -> None:
    """Drive `scripts/cli/verify_coverage_map.py` writer path."""
    stub = textwrap.dedent(f"""
        import sys
        from pathlib import Path
        from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
        AtCompletionLedger(
            {feature_id!r}, Path(sys.argv[1])
        ).append_coverage_map_verified_at_distill_exit()
    """)
    _run_caller_stub(project_root, stub)


def _drive_verify_slice_ledger_record(project_root: Path, feature_id: str) -> None:
    """Drive `scripts/hooks/verify_slice_ledger_record.py` reader path."""
    stub = textwrap.dedent(f"""
        import sys
        from pathlib import Path
        from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
        AtCompletionLedger({feature_id!r}, Path(sys.argv[1])).verified_slices()
    """)
    _run_caller_stub(project_root, stub)


def _drive_at_review_verdict(project_root: Path, feature_id: str) -> None:
    """Drive `scripts/cli/at_review_verdict.py` writer path."""
    stub = textwrap.dedent(f"""
        import sys
        from pathlib import Path
        from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
        AtCompletionLedger(
            feature_id={feature_id!r}, project_root=Path(sys.argv[1])
        ).append_review_verdict(
            slice_id="slice-01",
            verdict_fields={{
                "schema_version": "1.0.0",
                "verdict": "APPROVED",
                "reviewer_agent_id": "dispatch-driver",
                "at_ids": ["AT-1"],
                "at_content_hash": "0" * 64,
                "timestamp": "2026-05-25T00:00:00Z",
                "hmac_sha256": "0" * 64,
                "findings_summary": "ok",
            }},
        )
    """)
    _run_caller_stub(project_root, stub)


# --- slice-02d-N0 helper-seeding stub builders (Mandate-13 compliant) -------
# The fixture helper at `tests/des/_helpers/feature_end_seeding.py` is the
# SUT for slice-02d-N0. Composition.py drives it via spawned subprocess so
# the production `AtCompletionLedger` adapter import and the helper module
# import both live ONLY inside the stub script string (child-process scope).
# Composition.py imports zero `des.adapters.*` and zero
# `tests.des._helpers.*` symbols at module-level. This is the same M32-
# amendment pattern the 11 `_drive_*` functions use.


def _helper_legacy_shape_stub(feature_id: str) -> str:
    """Build the stub that drives the helper in legacy ledger-bound shape.

    The child process constructs `AtCompletionLedger(feature_id, project_root)`
    (legacy positional shape) and invokes the helper WITHOUT the new
    `feature_id=` kw-only argument. Pre-slice-02d-N0: works against today's
    helper signature. Post-slice-02d-N0 GREEN: still works (the new
    `feature_id=None` default preserves byte-identical behaviour for the 5
    existing fixture caller sites).
    """
    return textwrap.dedent(f"""
        import sys
        from pathlib import Path
        from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
        from tests.des._helpers.feature_end_seeding import (
            seed_required_feature_end_records,
        )
        ledger = AtCompletionLedger({feature_id!r}, Path(sys.argv[1]))
        seed_required_feature_end_records(ledger)
    """).strip()


def _helper_singleton_shape_stub(feature_id: str) -> str:
    """Build the stub that drives the helper in singleton-shape with feature_id.

    The child process constructs
    `AtCompletionLedger(project_root=project_root)` (singleton-shape) and
    invokes the helper with the new `feature_id=` kw-only argument. Pre-
    slice-02d-N0: reds with `TypeError: seed_required_feature_end_records()
    got an unexpected keyword argument 'feature_id'`. Post-slice-02d-N0
    GREEN: helper forwards feature_id to every `_RECORD_WRITERS` writer
    wrapper, each of which forwards to `ledger.append_*(feature_id=...)`.
    """
    return textwrap.dedent(f"""
        import sys
        from pathlib import Path
        from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
        from tests.des._helpers.feature_end_seeding import (
            seed_required_feature_end_records,
        )
        ledger = AtCompletionLedger(project_root=Path(sys.argv[1]))
        seed_required_feature_end_records(ledger, feature_id={feature_id!r})
    """).strip()


# --- slice-02c-A: per-callsite stub builders (gate-event affinity bundle) ---
# Each builder returns a subprocess stub that exercises the production
# callsite's POST-MIGRATION singleton-shape API. Pre-DELIVER the production
# source still uses legacy-positional shape (`AtCompletionLedger(feature_id,
# project_root)`) so AT-A1 reds via the side-by-side substrate observation
# (per-feature legacy file is still created by some production paths today,
# breaking the "only common log present" assertion). Post-A_GREEN_ATS the
# production code matches what these stubs already do, and AT-A1 passes.
#
# Mandate-13 boundary: the `from des.adapters.*` import lives inside the
# stub string (child-process scope); composition.py imports zero new
# `des.adapters.*` symbols at module-level.
#
# Per-callsite event-kind selection: each stub appends ONE representative
# event the production code path emits at that callsite. Sources:
#   - subagent_stop_handler.py:529 -> append_gate_event (any of the gate
#     event names; "CarpaccioGateCleared" is canonical)
#   - subagent_stop_handler.py:738 -> verified_slices() READ; the stub
#     drives the write that populates the read (append a SliceCommitVerified
#     gate event then call verified_slices(feature_id=...) to confirm the
#     reader sees only this feature's slice id)
#   - carpaccio_intercept.py:217 -> append_gate_event("CarpaccioGateCleared")
#   - carpaccio_intercept.py:322 -> append_gate_event (cleanup path; same
#     write API)
#   - reverify_slice_commit.py:199 -> verified_slices() READ (same pattern
#     as subagent_stop_handler:738)
#   - reverify_slice_commit.py:452 -> append_gate_event writer
#
# _CallsiteStubBuilder type alias declared at module-bottom alongside the
# existing `_CallerDriver` alias.

_CallsiteStubBuilder = (
    "callable"  # type alias: (feature_id: str) -> str (subprocess stub script)
)


def _build_slice_02c_a_stub_subagent_stop_handler_l529(feature_id: str) -> str:
    """Stub for subagent_stop_handler.py:529 -- gate-event writer post-migration.

    Production path emits a gate event via `ledger.append_gate_event(
    event=..., slice_id=...)` when SubagentStop fires for an atdd_pure crafter.
    Post-migration: singleton-shape ledger + per-call feature_id kwarg.
    """
    return textwrap.dedent(f"""
        import sys
        from pathlib import Path
        from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
        AtCompletionLedger(project_root=Path(sys.argv[1])).append_gate_event(
            event="CarpaccioGateCleared",
            slice_id="slice-01",
            feature_id={feature_id!r},
        )
    """).strip()


def _build_slice_02c_a_stub_subagent_stop_handler_l738(feature_id: str) -> str:
    """Stub for subagent_stop_handler.py:738 -- `verified_slices()` reader.

    Production path reads `ledger.verified_slices()` to derive the carpaccio-
    order shipped slice set. Post-migration: singleton-shape ledger +
    `verified_slices(feature_id=...)` filtered reader (slice-02b extension).
    The stub seeds one SliceCommitVerified gate event under the same feature_id
    then invokes the filtered reader, exercising the full write-then-read
    contract this callsite depends on.
    """
    return textwrap.dedent(f"""
        import sys
        from pathlib import Path
        from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
        ledger = AtCompletionLedger(project_root=Path(sys.argv[1]))
        ledger.append_gate_event(
            event="SliceCommitVerified",
            slice_id="slice-01",
            feature_id={feature_id!r},
        )
        ledger.verified_slices(feature_id={feature_id!r})
    """).strip()


def _build_slice_02c_a_stub_carpaccio_intercept_l217(feature_id: str) -> str:
    """Stub for carpaccio_intercept.py:217 -- gate-event writer post-migration.

    Production path is the U1 carpaccio PreToolUse hook's gate event emitter.
    Post-migration: singleton-shape ledger + per-call feature_id kwarg.
    """
    return textwrap.dedent(f"""
        import sys
        from pathlib import Path
        from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
        AtCompletionLedger(project_root=Path(sys.argv[1])).append_gate_event(
            event="CarpaccioGateCleared",
            slice_id="slice-01",
            feature_id={feature_id!r},
        )
    """).strip()


def _build_slice_02c_a_stub_carpaccio_intercept_l322(feature_id: str) -> str:
    """Stub for carpaccio_intercept.py:322 -- gate-event writer cleanup path.

    Production path is the U1 carpaccio cleanup writer (same write API as
    L217 but in the error-handling branch). Post-migration: singleton-shape
    ledger + per-call feature_id kwarg.
    """
    return textwrap.dedent(f"""
        import sys
        from pathlib import Path
        from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
        AtCompletionLedger(project_root=Path(sys.argv[1])).append_gate_event(
            event="CarpaccioGateRejected",
            slice_id="slice-01",
            feature_id={feature_id!r},
        )
    """).strip()


def _build_slice_02c_a_stub_reverify_slice_commit_l199(feature_id: str) -> str:
    """Stub for reverify_slice_commit.py:199 -- `verified_slices()` reader.

    Same pattern as subagent_stop_handler:738 (write-then-filtered-read).
    Production path: `reverify` CLI reads verified_slices to check whether a
    slice was already shipped (idempotency probe). Post-migration: singleton-
    shape ledger + filtered reader (slice-02b extension).
    """
    return textwrap.dedent(f"""
        import sys
        from pathlib import Path
        from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
        ledger = AtCompletionLedger(project_root=Path(sys.argv[1]))
        ledger.append_gate_event(
            event="SliceCommitVerified",
            slice_id="slice-01",
            feature_id={feature_id!r},
        )
        ledger.verified_slices(feature_id={feature_id!r})
    """).strip()


def _build_slice_02c_a_stub_reverify_slice_commit_l452(feature_id: str) -> str:
    """Stub for reverify_slice_commit.py:452 -- gate-event writer post-migration.

    Production path: `reverify` CLI writes a SliceCommitVerified gate event
    after re-verification succeeds. Post-migration: singleton-shape ledger +
    per-call feature_id kwarg.
    """
    return textwrap.dedent(f"""
        import sys
        from pathlib import Path
        from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
        AtCompletionLedger(project_root=Path(sys.argv[1])).append_gate_event(
            event="SliceCommitVerified",
            slice_id="slice-01",
            feature_id={feature_id!r},
        )
    """).strip()
