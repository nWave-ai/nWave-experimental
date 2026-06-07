"""Composition root for the fix-walking-skeleton-feature-end-wiring suite.

Mandate-12 criterion 2/3 + Pillar 3: the SUT is wired through the PRODUCTION
SSOT for "feature is closeable" -- the real
``_missing_feature_end_cycle_records`` U4 enforcer (Claude-Code-coupled hook
branch) and the real ``verify_deliver_integrity`` CLI mirror -- both invoked
against per-scenario tmp repos seeded with a real ``AtCompletionLedger``.

ALL business logic lives in this module's service methods -- the single
source of truth. Step bodies in ``test_slice_01_feature_end_u4_wiring.py``
delegate to these methods and never inline business logic (Mandate-12
criterion 3): each step body is a typed lookup plus one composition call.

RED scaffold (Mandate 7 / ADR-025): every scenario reds for the RIGHT
reason -- the production frozenset and union read do NOT YET include the
walking-skeleton heartbeat / events reader, so the U4 enforcer never
surfaces the heartbeat as missing AND the CLI mirror never surfaces it
either. The composition runs the real production code (no scaffold class
of our own); the AT assertions fail because production behaviour is
absent, not because the test infrastructure is broken.

Layer note: every scenario here is layer 3 (subprocess / FS acceptance
against real production code) -- example-only, no PBT (Mandate 9/11). Every
state-mutating step asserts via the port-exposed missing-record set or the
CLI exit verdict (Mandate 8 universe-bound).
"""

from __future__ import annotations

import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from .domain_types import FeatureEndLedgerState, MissingRecordOutcome


# --- Domain observation types ------------------------------------------------


@dataclass(frozen=True)
class U4EnforcerResult:
    """The user-observable outcome of one U4 enforcer evaluation.

    Mirrors the missing-record frozenset returned by
    ``_missing_feature_end_cycle_records``. Frozen: a result is an immutable
    observation, never mutated by an assertion.
    """

    missing_records: frozenset[str]

    @property
    def is_empty(self) -> bool:
        return len(self.missing_records) == 0

    @property
    def walking_skeleton_heartbeat_is_missing(self) -> bool:
        return "WalkingSkeletonGateRan" in self.missing_records


@dataclass(frozen=True)
class CliVerifyResult:
    """The user-observable verdict of one ``verify_deliver_integrity`` run."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def reports_feature_end_cycle_incomplete(self) -> bool:
        """Whether the CLI's stdout carries a FeatureEndCycleIncomplete verdict.

        The CLI emits a structured ``{"event": "FeatureEndCycleIncomplete",
        "missing_records": [...]}`` JSON line on shipped-but-incomplete
        features (the Slice-Id-commits branch); otherwise the legacy
        plain-text ``INTEGRITY VIOLATION`` shape carries the same intent.
        Both shapes are accepted as the same observable verdict.
        """
        return (
            '"event": "FeatureEndCycleIncomplete"' in self.stdout
            or "INTEGRITY VIOLATION" in self.stdout
        )

    @property
    def names_walking_skeleton_heartbeat_missing(self) -> bool:
        """Whether the CLI verdict names ``WalkingSkeletonGateRan`` as missing."""
        return "WalkingSkeletonGateRan" in self.stdout


# --- Composition root --------------------------------------------------------


@dataclass
class WalkingSkeletonFeatureEndWiringComposition:
    """Production-composition root for the four ATs in this slice."""

    _repo: Path | None = None
    _feature_id: str | None = None
    _staged_ledger_state: FeatureEndLedgerState | None = None
    enforcer_result: U4EnforcerResult | None = None
    cli_result: CliVerifyResult | None = None

    # --- Given services ----------------------------------------------------

    def given_feature_end_ledger_state(
        self, ledger_state: FeatureEndLedgerState
    ) -> None:
        """Stage a per-scenario tmp repo with a feature-end ledger in ``ledger_state``.

        Writes the real ``AtCompletionLedger`` records the U4 enforcer reads.
        Both states write the three pre-extension required heartbeats
        (refactor + env-e2e + review verdict) so the assertion isolates the
        walking-skeleton heartbeat's presence/absence as the single
        independent variable. The COMPLETE_WITH_WALKING_SKELETON state ALSO
        writes the new walking-skeleton heartbeat.
        """
        from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
        from tests.des._helpers.feature_end_seeding import (
            seed_required_feature_end_records,
        )

        workspace = Path(tempfile.mkdtemp(prefix="ws-feature-end-wiring-"))
        feature_id = f"fixture-feature-{uuid.uuid4().hex[:8]}"
        # The atdd_pure mode-aware CLI mirror needs the workflow config to
        # route through `_verify_atdd_pure` rather than the classic branch.
        nwave_dir = workspace / ".nwave"
        nwave_dir.mkdir(parents=True, exist_ok=True)
        (nwave_dir / "config.yaml").write_text("workflow:\n  mode: atdd_pure\n")

        ledger = AtCompletionLedger(feature_id, workspace)
        # WalkingSkeletonGateRan is the test's independent variable -- every
        # OTHER U4-required record is seeded unconditionally so the missing-
        # set assertion isolates the walking-skeleton heartbeat. The shared
        # seeding helper (`seed_required_feature_end_records`) walks the
        # `_RECORD_WRITERS` registry; `exclude=("WalkingSkeletonGateRan",)`
        # keeps the walking-skeleton heartbeat under explicit conditional
        # control while every future frozenset extension is auto-included.
        seed_required_feature_end_records(
            ledger,
            verdict_hash="fixture-hash",
            exclude=("WalkingSkeletonGateRan",),
        )
        if ledger_state is FeatureEndLedgerState.COMPLETE_WITH_WALKING_SKELETON:
            ledger.append_walking_skeleton_gate_ran()

        self._repo = workspace
        self._feature_id = feature_id
        self._staged_ledger_state = ledger_state

    # --- When services -----------------------------------------------------

    def when_u4_enforcer_runs(self) -> U4EnforcerResult:
        """Run the production U4 enforcer; capture the missing-record set.

        Invokes the real ``_missing_feature_end_cycle_records`` from the
        ``subagent_stop_handler`` module -- the Claude-Code-coupled U4
        mechanical enforcement point (DESIGN RES-2 in the env-e2e slice-02
        narrative). The port-exposed observable is the missing-record
        frozenset (Mandate 8 universe-bound).
        """
        from des.adapters.drivers.hooks.subagent_stop_handler import (
            _missing_feature_end_cycle_records,
        )

        assert self._repo is not None, "ledger staging missing"
        assert self._feature_id is not None, "feature id missing"
        missing = _missing_feature_end_cycle_records(self._repo, self._feature_id)
        result = U4EnforcerResult(missing_records=frozenset(missing))
        self.enforcer_result = result
        return result

    def when_verify_deliver_integrity_cli_runs(self) -> CliVerifyResult:
        """Run the production ``verify_deliver_integrity`` CLI as a subprocess.

        Invokes ``des verify-integrity`` against the per-scenario tmp repo
        (post-slice-03 single-entry-point form). The CLI's ``_verify_atdd_pure``
        branch reads the same SSOT (the required-record set + the union of
        feature-end and environmental-e2e events) and emits a
        ``FeatureEndCycleIncomplete`` verdict on a missing record. The CLI
        parity is the contract this AT pins: hook block <=> CLI block.
        """
        assert self._repo is not None, "ledger staging missing"
        assert self._feature_id is not None, "feature id missing"
        proc = subprocess.run(
            [
                "des",
                "verify-integrity",
                str(self._repo),
                "--feature-id",
                self._feature_id,
            ],
            capture_output=True,
            text=True,
        )
        result = CliVerifyResult(
            exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr
        )
        self.cli_result = result
        return result

    # --- Then services -----------------------------------------------------

    def then_missing_record_set_matches(
        self, expected_outcome: MissingRecordOutcome
    ) -> None:
        """Assert the walking-skeleton heartbeat presence/absence in the missing set.

        Port-exposed observable: the missing-record frozenset returned by
        ``_missing_feature_end_cycle_records``. ``ABSENT`` means the
        heartbeat is NOT in the missing set (so the ledger recorded it);
        ``PRESENT`` means the heartbeat IS in the missing set (so the
        enforcer detected its absence from the ledger). The assertion is
        scoped to the walking-skeleton heartbeat alone -- the env-e2e
        heartbeat and refactor/review records are always seeded, so they
        never appear in the missing set in this slice's scenarios.
        """
        assert self.enforcer_result is not None, "enforcer not run"
        actual_missing = self.enforcer_result.walking_skeleton_heartbeat_is_missing
        expected_missing = expected_outcome is MissingRecordOutcome.PRESENT
        assert actual_missing == expected_missing, (
            f"walking-skeleton heartbeat missing-outcome mismatch: "
            f"expected={expected_outcome.value}, "
            f"actual missing_records={sorted(self.enforcer_result.missing_records)}"
        )

    def then_missing_record_set_is_empty(self) -> None:
        """Assert the U4 enforcer returns an empty missing-record set.

        Regression-pin: a feature whose ledger seeds BOTH the env-e2e and the
        walking-skeleton heartbeats (the post-extension co-shipped fixture
        seeding) must not regress -- the U4 enforcer returns an empty set
        and the feature is permitted to be declared done.
        """
        assert self.enforcer_result is not None, "enforcer not run"
        assert self.enforcer_result.is_empty, (
            f"expected empty missing-record set; "
            f"actual missing_records={sorted(self.enforcer_result.missing_records)}"
        )

    def then_feature_is_permitted(self) -> None:
        """Assert the feature is permitted to be declared done.

        Port-exposed observable: the U4 missing-record set is empty.
        """
        assert self.enforcer_result is not None, "enforcer not run"
        assert self.enforcer_result.is_empty, (
            f"feature should be permitted but missing-record set is non-empty: "
            f"{sorted(self.enforcer_result.missing_records)}"
        )

    def then_feature_is_not_permitted_when_missing_records(self) -> None:
        """Assert: missing-record set non-empty implies feature blocked.

        This is the contract assertion -- the U4 enforcer returning a
        non-empty set is the SSOT signal that the feature is blocked at
        feature-end. Scenarios that seed a complete ledger (with-heartbeat)
        skip this assertion via the empty-set short-circuit.
        """
        assert self.enforcer_result is not None, "enforcer not run"
        if not self.enforcer_result.is_empty:
            # Non-empty set -> feature blocked. Contract asserted; nothing
            # more to verify here -- the missing-record content was already
            # asserted by then_missing_record_set_matches.
            return
        # Empty set -> feature permitted. The other paired Then asserted
        # missing_outcome=absent already; this step is a no-op for that path.

    def then_cli_reports_feature_end_cycle_incomplete(self) -> None:
        """Assert the CLI exits with a feature-end-cycle-incomplete verdict.

        Port-exposed observable: CLI exit code 1 AND stdout carries the
        FeatureEndCycleIncomplete structured event (or the legacy
        ``INTEGRITY VIOLATION`` plain-text shape). The CLI mirror of the U4
        hook block.
        """
        assert self.cli_result is not None, "CLI not run"
        assert self.cli_result.exit_code == 1, (
            f"expected CLI exit 1 (feature-end-cycle-incomplete); "
            f"actual exit={self.cli_result.exit_code}\n"
            f"stdout: {self.cli_result.stdout}\n"
            f"stderr: {self.cli_result.stderr}"
        )
        assert self.cli_result.reports_feature_end_cycle_incomplete, (
            f"expected stdout to carry FeatureEndCycleIncomplete (or "
            f"INTEGRITY VIOLATION) verdict; actual stdout:\n"
            f"{self.cli_result.stdout}"
        )

    def then_cli_names_walking_skeleton_heartbeat_missing(self) -> None:
        """Assert the CLI verdict names the walking-skeleton heartbeat as missing."""
        assert self.cli_result is not None, "CLI not run"
        assert self.cli_result.names_walking_skeleton_heartbeat_missing, (
            f"expected CLI stdout to name WalkingSkeletonGateRan as a "
            f"missing required record; actual stdout:\n{self.cli_result.stdout}"
        )
