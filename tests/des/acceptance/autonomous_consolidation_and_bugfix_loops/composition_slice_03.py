"""Composition root + shared fixtures for autonomous-consolidation-and-bugfix-loops
slice-03 (the bugfix loop drains the defect queue as a pipeline -- charter
`the-bugfix-loop-drains-the-queue-as-a-pipeline.md`, feature-delta Slice Plan
row slice-03, Locked Decision D-4).

Pillar 3 (App as in production): the SUT is the REAL
``des bugfix-pipeline-tick`` CLI entry (``des.cli.bugfix_pipeline_tick.main``),
driven IN-PROCESS once per stage-transition tick via the SAME reusable
in-process driving-port helper the shipped corpus already uses
(``run_cli_in_process`` -- ``tests/common/in_process_cli.py``). This module
NEVER imports the not-yet-created domain pipeline-evaluation seam
(``des.domain.bugfix_pipeline``) -- only the real CLI entry point is driven.
``AtCompletionLedger`` is imported ONLY to OBSERVE the resulting records (the
S2 tolerable-variant, same as the slice-01/slice-02 siblings) -- it is
substrate observation, NOT the SUT.

── THE CONTROLLABLE CLOCK (deterministic, NO real sleep) ──
Every tick supplies an explicit ``--now`` instant computed from a FIXED base
timestamp plus a caller-chosen minute offset -- the same mechanism slice-02
established. A multi-tick sequence models several defects being worked
concurrently without a single real-time wait.

── THE TWO-LANE INVARIANT (D-4) ──
Cloud-lane stages (RCA / charter-authoring / AT-authoring) are fired with NO
concurrency ceiling -- multiple defects may have an open cloud-lane stage at
once. Box-lane stages (RED-seal / crafter-GREEN / Vera-examine /
commit-slice) are expected to be admitted ONLY when no other defect already
holds one open -- a second concurrent attempt should be observed as a
`BoxLaneEntryDeferred` record, never a silent admission and never a silent
drop.

── STEP-BODY ARITHMETIC LIVES HERE (Mandate-12 criterion 3) ──
Most scenarios drive the fixture through ONE atomic call per Gherkin line
(`start_stage` / `complete_stage` / `fail_stage` / `claim_drained`) --
concrete, readable, one action per line (Pillar 7). The two scenarios with
genuine multi-tick SEQUENCING arithmetic (walking a full 7-stage chain;
several defects serialized one after another across an extended drain) get
a dedicated composition method (`drive_full_chain`,
`sample_box_lane_across_drain`) so that arithmetic never leaks into a step
body.

── Mechanical assertion (Mandate-13 invariant 5) ──
Python + filesystem only, cross-OS. No git subprocess needed for this slice
-- only the ledger + an injected clock.

Universe (Mandate 8): {outcome.cloud_lane_concurrent_count,
outcome.box_lane_concurrent_count, outcome.box_lane_activity_observed,
outcome.box_lane_entry_deferred, outcome.deferred_reason_named,
outcome.full_chain_traceable, outcome.slice_commit_verified_present,
outcome.drain_claim_rejected, outcome.rejection_reason_named,
outcome.mid_pipeline_failure_recorded, outcome.box_lane_freed_after_failure,
outcome.new_record_count}. Internal fields (Popen handle, argv list, raw
ledger path) NEVER appear.

Layer 3/4 (real filesystem + real ledger JSONL + real in-process CLI
invocation against tmp_path): example-only (Mandate 9 v2 -- @real-io =>
example-based, NOT PBT). Sad paths explicit (Mandate 11). No PBT machinery.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Observation-only substrate reader (NOT the SUT). Reads back the appended
# records -- the S2 tolerable-variant, same as the slice-01 / slice-02
# siblings.
from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger

# The REAL `des bugfix-pipeline-tick` CLI entry, driven IN-PROCESS via the
# shared reusable driving-port helper (node-C enabler `run_cli_in_process`) --
# the same faithful in-process pattern the shipped corpus already migrated
# to (post `corpus-migration-in-process`).
from des.cli.bugfix_pipeline_tick import main as _bugfix_pipeline_tick_main
from tests.common.in_process_cli import run_cli_in_process

from .steps.domain_types_slice_03 import (
    FULL_CHAIN_ORDER,
    DefectId,
    FeatureId,
    PipelineOutcome,
    PipelineStage,
)


# The feature this suite builds a synthetic multi-defect drain sequence for.
# Distinct from the carpaccio `@slice-03` tag on the .feature scenarios
# themselves; this constant is an arbitrary fixture key inside the fake
# ledger namespace, mirroring slice-01/slice-02's `-demo` disambiguation.
_FEATURE_ID = FeatureId("autonomous-consolidation-and-bugfix-loops-demo-slice03")

# The controllable-clock base instant every tick's minute offset is computed
# from. Arbitrary and fixed -- the point is determinism, not calendar realism.
_BASE_INSTANT = datetime(2026, 7, 1, 10, 0, 0, tzinfo=timezone.utc)

_STARTED = "PipelineStageStarted"
_COMPLETED = "PipelineStageCompleted"
_FAILED = "PipelineStageFailed"
_DEFERRED = "BoxLaneEntryDeferred"
_DRAIN_REJECTED = "DrainClaimRejectedNoAttestation"

_PIPELINE_EVENTS = frozenset(
    {_STARTED, _COMPLETED, _FAILED, _DEFERRED, _DRAIN_REJECTED}
)

_BOX_LANE_STAGE_VALUES = frozenset(
    {
        PipelineStage.RED_SEAL.value,
        PipelineStage.CRAFTER_GREEN.value,
        PipelineStage.VERA_EXAMINE.value,
        PipelineStage.COMMIT_SLICE.value,
    }
)


def _at_minute(offset_minutes: float) -> str:
    """An ISO-8601 instant `offset_minutes` after the fixed base -- the
    controllable clock. Pure function, no real sleep.
    """
    moment = _BASE_INSTANT + timedelta(minutes=offset_minutes)
    return moment.isoformat().replace("+00:00", "Z")


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass
class BugfixPipelineFixture:
    """Composition-root service for autonomous-consolidation-and-bugfix-loops
    slice-03 ATs.

    Pillar 3: fires one or more REAL ``des bugfix-pipeline-tick`` CLI ticks
    in-process against a synthetic controllable-clock timeline, then
    interprets the AT-completion ledger's OWN recorded content into the
    port-exposed ``PipelineOutcome`` -- never re-simulating the pipeline
    logic inside the test (the observable is what the ledger ACTUALLY says,
    not what the fixture computed it should say).

    Mandate-12 criterion 3: every public method is the SSOT for one piece of
    business logic. Step bodies do a typed lookup + one method call; nothing
    more.
    """

    _repo: Path = field(init=False)

    def __init__(self, tmp_path: Path) -> None:
        self._repo = tmp_path / "loop-repo"
        self._repo.mkdir(parents=True, exist_ok=True)

    # --- driving-port invocation (the REAL CLI, one tick at a time) --------

    def _fire_one_tick(
        self,
        *,
        defect_id: DefectId,
        action: str,
        stage: PipelineStage | None,
        at_minute: float,
        reason: str | None,
    ) -> None:
        """Fire the REAL ``des bugfix-pipeline-tick`` entry once, in-process."""
        argv = [
            "--feature-id",
            str(_FEATURE_ID),
            "--project-root",
            str(self._repo),
            "--defect-id",
            str(defect_id),
            "--action",
            action,
            "--now",
            _at_minute(at_minute),
        ]
        if stage is not None:
            argv += ["--stage", stage.value]
        if reason is not None:
            argv += ["--reason", reason]
        run_cli_in_process(argv, cwd=self._repo, main=_bugfix_pipeline_tick_main)

    # --- atomic actions (one Gherkin line -> one call, Mandate-12 crit. 3) --

    def start_stage(
        self, defect_id: DefectId, stage: PipelineStage, at_minute: float
    ) -> None:
        self._fire_one_tick(
            defect_id=defect_id,
            action="stage-started",
            stage=stage,
            at_minute=at_minute,
            reason=None,
        )

    def complete_stage(
        self, defect_id: DefectId, stage: PipelineStage, at_minute: float
    ) -> None:
        self._fire_one_tick(
            defect_id=defect_id,
            action="stage-completed",
            stage=stage,
            at_minute=at_minute,
            reason=None,
        )

    def fail_stage(
        self,
        defect_id: DefectId,
        stage: PipelineStage,
        at_minute: float,
        reason: str,
    ) -> None:
        self._fire_one_tick(
            defect_id=defect_id,
            action="stage-failed",
            stage=stage,
            at_minute=at_minute,
            reason=reason,
        )

    def claim_drained(self, defect_id: DefectId, at_minute: float) -> None:
        self._fire_one_tick(
            defect_id=defect_id,
            action="claim-drained",
            stage=None,
            at_minute=at_minute,
            reason=None,
        )

    def claim_drained_and_sample(
        self, defect_id: DefectId, at_minute: float
    ) -> PipelineOutcome:
        """AT-14's shape: fire the claim, then read back the ledger's own
        verdict on it -- ONE call for the step body (Mandate-12 crit. 3).
        """
        self.claim_drained(defect_id, at_minute)
        return self.sample_for_defect(defect_id, at_minute)

    # --- outcome sampling ----------------------------------------------------

    def sample_concurrency_at(self, sample_at_minute: float) -> PipelineOutcome:
        """AT-11/AT-12/AT-16's shape: interpret the ledger's cumulative
        content as of ``sample_at_minute`` -- how many defects hold an OPEN
        cloud-lane / box-lane stage at that instant, plus every
        content-presence observable (deferred, failed, freed-after-failure).
        """
        return self._interpret(self._read_all(), sample_at_minute, focus_defect=None)

    def sample_for_defect(
        self, defect_id: DefectId, sample_at_minute: float
    ) -> PipelineOutcome:
        """AT-13/AT-14's shape: as ``sample_concurrency_at``, but ALSO
        resolves the full-chain-traceability and commit-slice-attestation
        observables for ONE focused defect.
        """
        return self._interpret(
            self._read_all(), sample_at_minute, focus_defect=defect_id
        )

    # --- scenario-shaped sequence builders (genuine multi-tick arithmetic;
    # Mandate-12 criterion 3 keeps this OUT of step bodies) -------------------

    def drive_full_chain(
        self, defect_id: DefectId, start_at_minute: float
    ) -> PipelineOutcome:
        """AT-13's shape: walk ONE defect through the full 7-stage chain,
        started-then-completed for each stage in FULL_CHAIN_ORDER.
        """
        cursor = start_at_minute
        for stage in FULL_CHAIN_ORDER:
            self.start_stage(defect_id, stage, cursor)
            cursor += 1
            self.complete_stage(defect_id, stage, cursor)
            cursor += 1
        return self.sample_for_defect(defect_id, cursor)

    def drive_serialized_box_lane_walk(
        self,
        defects: list[DefectId],
        stage: PipelineStage,
        start_at_minute: float,
        gap_minutes: float,
    ) -> None:
        """AT-15's shape: several defects walk the SAME box-lane stage one
        after another (start, complete, then the next starts) across an
        extended drain. Driver-only -- no outcome returned -- so the Then
        step can sample concurrency at WHATEVER instant its Scenario
        Outline Example names, proving the box lane never exceeds 1 at ANY
        point through the whole sequence, not merely at a single
        hand-picked instant.
        """
        cursor = start_at_minute
        for defect_id in defects:
            self.start_stage(defect_id, stage, cursor)
            cursor += gap_minutes / 2
            self.complete_stage(defect_id, stage, cursor)
            cursor += gap_minutes / 2

    # --- ledger observation --------------------------------------------------

    def _read_all(self) -> list[dict]:
        """Read every record for this fixture's ledger (port read, port-exposed)."""
        ledger = AtCompletionLedger(_FEATURE_ID, self._repo)
        try:
            return ledger.read_records()
        except Exception:
            return []

    def _interpret(
        self,
        records: list[dict],
        sample_at_minute: float,
        *,
        focus_defect: DefectId | None,
    ) -> PipelineOutcome:
        """Build the port-exposed observable outcome from the ledger's OWN
        recorded content -- never from the fixture's own tick-scheduling
        bookkeeping. This is the observer half of the D-8 no-orphan /
        negative-oracle discipline: the outcome is what the ledger actually
        proves, not what the test expected to have happened.
        """
        pipeline_records = [r for r in records if r.get("event") in _PIPELINE_EVENTS]
        sample_ts = _at_minute(sample_at_minute)
        sample_dt = _parse_ts(sample_ts)

        # --- concurrency at the sampled instant: last event per defect_id,
        # among records timestamped at-or-before the sample instant.
        by_defect: dict[str, list[dict]] = {}
        for record in pipeline_records:
            ts = record.get("timestamp")
            if not isinstance(ts, str):
                continue
            if _parse_ts(ts) > sample_dt:
                continue
            if record.get("event") not in (_STARTED, _COMPLETED, _FAILED):
                continue
            by_defect.setdefault(record.get("defect_id", ""), []).append(record)

        cloud_open = 0
        box_open = 0
        for defect_records in by_defect.values():
            last = sorted(defect_records, key=lambda r: r.get("seq", 0))[-1]
            if last.get("event") != _STARTED:
                continue
            stage_value = last.get("stage")
            if stage_value in _BOX_LANE_STAGE_VALUES:
                box_open += 1
            elif stage_value is not None:
                cloud_open += 1

        box_activity = any(
            r.get("event") == _STARTED and r.get("stage") in _BOX_LANE_STAGE_VALUES
            for r in pipeline_records
        )

        deferred_records = [r for r in pipeline_records if r.get("event") == _DEFERRED]
        deferred = bool(deferred_records)
        deferred_reason_named = deferred and all(
            bool(r.get("reason")) for r in deferred_records
        )

        rejected_records = [
            r for r in pipeline_records if r.get("event") == _DRAIN_REJECTED
        ]
        drain_claim_rejected = bool(rejected_records)
        rejection_reason_named = drain_claim_rejected and all(
            bool(r.get("reason")) for r in rejected_records
        )

        failed_records = [r for r in pipeline_records if r.get("event") == _FAILED]
        mid_pipeline_failure_recorded = bool(failed_records) and all(
            bool(r.get("reason")) for r in failed_records
        )

        # box_lane_freed_after_failure: a box-lane PipelineStageStarted with a
        # HIGHER seq than a box-lane PipelineStageFailed, belonging to a
        # DIFFERENT defect, with NO BoxLaneEntryDeferred at that same later
        # seq -- proving the later entry was ADMITTED, not deferred.
        box_lane_freed_after_failure = False
        if failed_records:
            last_failure_seq = max(r.get("seq", -1) for r in failed_records)
            failed_defects = {r.get("defect_id") for r in failed_records}
            later_admits = [
                r
                for r in pipeline_records
                if r.get("event") == _STARTED
                and r.get("stage") in _BOX_LANE_STAGE_VALUES
                and r.get("seq", -1) > last_failure_seq
                and r.get("defect_id") not in failed_defects
            ]
            later_deferral_seqs = {
                r.get("seq")
                for r in deferred_records
                if r.get("seq", -1) > last_failure_seq
            }
            box_lane_freed_after_failure = any(
                r.get("seq") not in later_deferral_seqs for r in later_admits
            )

        # full_chain_traceable / slice_commit_verified_present: focused on
        # ONE defect_id (AT-13/AT-14's shape).
        full_chain_traceable = False
        slice_commit_verified_present = False
        if focus_defect is not None:
            completed = [
                r
                for r in pipeline_records
                if r.get("event") == _COMPLETED
                and r.get("defect_id") == str(focus_defect)
            ]
            completed_sorted = sorted(completed, key=lambda r: r.get("seq", 0))
            completed_stage_sequence = [r.get("stage") for r in completed_sorted]
            expected_sequence = [s.value for s in FULL_CHAIN_ORDER]
            full_chain_traceable = completed_stage_sequence == expected_sequence
            slice_commit_verified_present = (
                PipelineStage.COMMIT_SLICE.value in completed_stage_sequence
            )

        return PipelineOutcome(
            cloud_lane_concurrent_count=cloud_open,
            box_lane_concurrent_count=box_open,
            box_lane_activity_observed=box_activity,
            box_lane_entry_deferred=deferred,
            deferred_reason_named=deferred_reason_named,
            full_chain_traceable=full_chain_traceable,
            slice_commit_verified_present=slice_commit_verified_present,
            drain_claim_rejected=drain_claim_rejected,
            rejection_reason_named=rejection_reason_named,
            mid_pipeline_failure_recorded=mid_pipeline_failure_recorded,
            box_lane_freed_after_failure=box_lane_freed_after_failure,
            new_record_count=len(pipeline_records),
        )


@pytest.fixture
def pipeline_fixture(tmp_path) -> BugfixPipelineFixture:
    """The single composition-root service all slice-03 step methods delegate to."""
    return BugfixPipelineFixture(tmp_path)


@pytest.fixture
def state_03() -> dict:
    """Per-scenario scratchpad: `outcome`, `defect_id` (AT-13/14's focus)."""
    return {}


__all__ = [
    "BugfixPipelineFixture",
]
