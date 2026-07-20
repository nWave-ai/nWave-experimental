"""Composition root + shared fixtures for autonomous-consolidation-and-bugfix-loops
slice-04 (trunk-health signals become queue items that never vanish -- charter
`trunk-health-signals-become-queue-items-that-never-vanish.md`, feature-delta
Slice Plan row slice-04, building on Locked Decision D-4's shared pipeline).

Pillar 3 (App as in production): the SUT is the REAL
``des consolidation-signal-tick`` CLI entry
(``des.cli.consolidation_signal_tick.main``), driven IN-PROCESS once per
detected signal via the SAME reusable in-process driving-port helper the
shipped corpus already uses (``run_cli_in_process`` --
``tests/common/in_process_cli.py``). This module NEVER imports the not-yet-
created domain intake seam (``des.domain.consolidation_queue_intake``) --
only the real CLI entry point is driven. ``AtCompletionLedger`` is imported
ONLY to OBSERVE the resulting records (the S2 tolerable-variant, same as the
slice-01/02/03 siblings) -- it is substrate observation, NOT the SUT.

── REUSE, DON'T REBUILD, MECHANICALLY PROVEN (D-4/D-19) ──
AT-19's ``drive_rest_of_shared_pipeline`` fires the SIBLING slice-03 driving
port (``des.cli.bugfix_pipeline_tick.main``) DIRECTLY against the SAME
defect_id this slice's intake queued -- the mechanical proof that a queued
signal flows through the SAME shared pipeline, not a lookalike duplicate.
``PipelineStage`` / ``FULL_CHAIN_ORDER`` are imported from
``domain_types_slice_03`` UNMODIFIED, never re-declared here.

── THE CONTROLLABLE CLOCK (deterministic, NO real sleep) ──
Every tick supplies an explicit ``--now`` instant computed from a FIXED base
timestamp plus a caller-chosen minute offset -- the same mechanism
slice-02/slice-03 established.

── THE DEFECT_ID DERIVATION (DELIVER-pinned assumption, mirrored here for
test-side scoping only -- the domain seam itself owns this derivation) ──
``consolidation-{signal_type}-{signal_key}`` -- deterministic, so the SAME
signal re-detected twice derives the SAME defect_id (the idempotency check
DELIVER's domain seam performs), and two DIFFERENT signal_keys of the SAME
signal_type derive two DIFFERENT defect_ids (AT-22's discriminator).

── Mechanical assertion (Mandate-13 invariant 5) ──
Python + filesystem only, cross-OS. No git subprocess needed for this
slice's ATs -- only the ledger + an injected clock.

Universe (Mandate 8): {outcome.queue_item_count, outcome.traceable_to_signal,
outcome.full_chain_traceable, outcome.slice_commit_verified_present,
outcome.intake_rejected, outcome.rejection_reason_named}. Internal fields
(Popen handle, argv list, raw ledger path, the derived defect_id string)
NEVER appear.

Layer 3/4 (real filesystem + real ledger JSONL + real in-process CLI
invocation against tmp_path): example-only (Mandate 9 v2 -- @real-io =>
example-based, NOT PBT). Sad paths explicit (Mandate 11). No PBT machinery.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Observation-only substrate reader (NOT the SUT). Reads back the appended
# records -- the S2 tolerable-variant, same as the slice-01/02/03 siblings.
from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger

# The SIBLING slice-03 driving port, reused DIRECTLY (AT-19's mechanical
# reuse proof) -- never a duplicate pipeline entry.
from des.cli.bugfix_pipeline_tick import main as _bugfix_pipeline_tick_main

# The REAL `des consolidation-signal-tick` CLI entry, driven IN-PROCESS via
# the shared reusable driving-port helper -- the same faithful in-process
# pattern the shipped corpus already migrated to.
from des.cli.consolidation_signal_tick import main as _consolidation_signal_tick_main
from tests.common.in_process_cli import run_cli_in_process

from .steps.domain_types_slice_03 import FULL_CHAIN_ORDER, PipelineStage
from .steps.domain_types_slice_04 import SUPPORTED_SIGNAL_TYPE_VALUES, IntakeOutcome


# The feature this suite builds a synthetic multi-signal intake sequence
# for. Distinct from the carpaccio `@slice-04` tag on the .feature scenarios
# themselves; this constant is an arbitrary fixture key inside the fake
# ledger namespace, mirroring slice-01/02/03's `-demo` disambiguation.
_FEATURE_ID = "autonomous-consolidation-and-bugfix-loops-demo-slice04"

# The controllable-clock base instant every tick's minute offset is computed
# from. Arbitrary and fixed -- the point is determinism, not calendar realism.
_BASE_INSTANT = datetime(2026, 7, 1, 10, 0, 0, tzinfo=timezone.utc)

_STARTED = "PipelineStageStarted"
_COMPLETED = "PipelineStageCompleted"
_REJECTED = "ConsolidationSignalIntakeRejected"

_INTAKE_EVENTS = frozenset({_STARTED, _COMPLETED, _REJECTED})

_CONSOLIDATION_DEFECT_PREFIX = "consolidation-"


def _at_minute(offset_minutes: float) -> str:
    """An ISO-8601 instant `offset_minutes` after the fixed base -- the
    controllable clock. Pure function, no real sleep.
    """
    moment = _BASE_INSTANT + timedelta(minutes=offset_minutes)
    return moment.isoformat().replace("+00:00", "Z")


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _derive_defect_id(signal_type: str, signal_key: str) -> str:
    """The SAME deterministic derivation the DELIVER-pinned domain seam
    performs (`consolidation-{signal_type}-{signal_key}`) -- mirrored here
    ONLY for test-side ledger scoping, never imported from production (the
    seam does not exist yet).
    """
    return f"{_CONSOLIDATION_DEFECT_PREFIX}{signal_type}-{signal_key}"


@dataclass
class ConsolidationIntakeFixture:
    """Composition-root service for autonomous-consolidation-and-bugfix-loops
    slice-04 ATs.

    Pillar 3: fires one or more REAL ``des consolidation-signal-tick`` CLI
    ticks in-process against a synthetic controllable-clock timeline, then
    interprets the AT-completion ledger's OWN recorded content into the
    port-exposed ``IntakeOutcome`` -- never re-simulating the intake logic
    inside the test (the observable is what the ledger ACTUALLY says, not
    what the fixture computed it should say).

    Mandate-12 criterion 3: every public method is the SSOT for one piece of
    business logic. Step bodies do a typed lookup + one method call; nothing
    more.
    """

    _repo: Path = field(init=False)

    def __init__(self, tmp_path: Path) -> None:
        self._repo = tmp_path / "loop-repo"
        self._repo.mkdir(parents=True, exist_ok=True)

    # --- driving-port invocation (the REAL CLI, one signal at a time) ------

    def detect_signal(
        self, signal_type: str, signal_key: str, at_minute: float
    ) -> None:
        """Fire the REAL ``des consolidation-signal-tick`` entry once,
        in-process -- one Gherkin line, one call (Mandate-12 criterion 3).
        """
        argv = [
            "--feature-id",
            _FEATURE_ID,
            "--project-root",
            str(self._repo),
            "--signal-type",
            signal_type,
            "--signal-key",
            signal_key,
            "--now",
            _at_minute(at_minute),
        ]
        run_cli_in_process(argv, cwd=self._repo, main=_consolidation_signal_tick_main)

    def detect_unsupported_signal_and_capture_cli(
        self, signal_type: str, signal_key: str, at_minute: float
    ) -> IntakeOutcome:
        """AT-21's shape (EXAMINE fix, Vera FAIL -- real-CLI-surface
        defect): fire the REAL CLI directly, capturing its exit code AND
        emitted stdout -- not merely reading the ledger. The defect Vera
        found was the CLI-FACING surface staying silent (exit 0) on a
        rejection the ledger already recorded correctly; a caller who never
        reads the ledger must still see the rejection fail loudly (D-8) on
        the ONLY surface it actually watches.
        """
        argv = [
            "--feature-id",
            _FEATURE_ID,
            "--project-root",
            str(self._repo),
            "--signal-type",
            signal_type,
            "--signal-key",
            signal_key,
            "--now",
            _at_minute(at_minute),
        ]
        exit_code, stdout, _stderr = run_cli_in_process(
            argv, cwd=self._repo, main=_consolidation_signal_tick_main
        )
        ledger_outcome = self.sample_for_signal(signal_type, signal_key, at_minute)
        return dataclasses.replace(
            ledger_outcome,
            cli_exit_code=exit_code,
            cli_output_names_unsupported_type=signal_type in stdout,
            cli_output_names_supported_set=all(
                value in stdout for value in SUPPORTED_SIGNAL_TYPE_VALUES
            ),
        )

    def drive_rest_of_shared_pipeline(
        self, signal_type: str, signal_key: str, start_at_minute: float
    ) -> IntakeOutcome:
        """AT-19's shape: after intake queued the signal's item at RCA, walk
        the REMAINING stages of the SAME shared bugfix-pipeline CLI slice-03
        built (charter-authoring -> ... -> commit-slice) by firing the
        SIBLING driving port DIRECTLY -- the mechanical proof of reuse
        (D-19), not merely an assertion.
        """
        defect_id = _derive_defect_id(signal_type, signal_key)
        cursor = start_at_minute
        self._fire_bugfix_pipeline_tick(
            defect_id, "stage-completed", PipelineStage.RCA, cursor
        )
        cursor += 1
        for stage in FULL_CHAIN_ORDER[1:]:
            self._fire_bugfix_pipeline_tick(defect_id, "stage-started", stage, cursor)
            cursor += 1
            self._fire_bugfix_pipeline_tick(defect_id, "stage-completed", stage, cursor)
            cursor += 1
        return self.sample_for_signal(signal_type, signal_key, cursor)

    def _fire_bugfix_pipeline_tick(
        self,
        defect_id: str,
        action: str,
        stage: PipelineStage,
        at_minute: float,
    ) -> None:
        argv = [
            "--feature-id",
            _FEATURE_ID,
            "--project-root",
            str(self._repo),
            "--defect-id",
            defect_id,
            "--action",
            action,
            "--stage",
            stage.value,
            "--now",
            _at_minute(at_minute),
        ]
        run_cli_in_process(argv, cwd=self._repo, main=_bugfix_pipeline_tick_main)

    # --- outcome sampling ----------------------------------------------------

    def sample_for_signal(
        self, signal_type: str, signal_key: str, sample_at_minute: float
    ) -> IntakeOutcome:
        """AT-17/AT-19/AT-20/AT-21's shape: interpret the ledger's cumulative
        content as of ``sample_at_minute``, scoped to the ONE defect_id
        derived from ``(signal_type, signal_key)`` -- "does THIS signal have
        exactly one queue item, not zero and not two?"
        """
        defect_id = _derive_defect_id(signal_type, signal_key)
        return self._interpret(
            self._read_all(), sample_at_minute, scope_defect_id=defect_id
        )

    def sample_all_signals(self, sample_at_minute: float) -> IntakeOutcome:
        """AT-18/AT-22's shape: interpret the ledger's cumulative content as
        of ``sample_at_minute`` across EVERY consolidation-signal-derived
        defect_id -- "how many distinct queue items exist across every
        signal detected so far?"
        """
        return self._interpret(self._read_all(), sample_at_minute, scope_defect_id=None)

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
        scope_defect_id: str | None,
    ) -> IntakeOutcome:
        """Build the port-exposed observable outcome from the ledger's OWN
        recorded content -- never from the fixture's own tick-scheduling
        bookkeeping. This is the observer half of the D-8 no-orphan /
        negative-oracle discipline: the outcome is what the ledger actually
        proves, not what the test expected to have happened.
        """
        intake_records = [r for r in records if r.get("event") in _INTAKE_EVENTS]
        sample_dt = _parse_ts(_at_minute(sample_at_minute))
        up_to_sample = [
            r
            for r in intake_records
            if isinstance(r.get("timestamp"), str)
            and _parse_ts(r["timestamp"]) <= sample_dt
        ]
        if scope_defect_id is not None:
            up_to_sample = [
                r for r in up_to_sample if r.get("defect_id") == scope_defect_id
            ]
        else:
            up_to_sample = [
                r
                for r in up_to_sample
                if isinstance(r.get("defect_id"), str)
                and r["defect_id"].startswith(_CONSOLIDATION_DEFECT_PREFIX)
            ]

        started_rca = [
            r
            for r in up_to_sample
            if r.get("event") == _STARTED and r.get("stage") == PipelineStage.RCA.value
        ]
        distinct_queued_defects = {r.get("defect_id") for r in started_rca}
        queue_item_count = len(distinct_queued_defects)

        traceable_to_signal = False
        if scope_defect_id is not None and queue_item_count == 1:
            (record,) = started_rca
            reason = record.get("reason") or ""
            traceable_to_signal = bool(reason)

        completed = [r for r in up_to_sample if r.get("event") == _COMPLETED]
        completed_sorted = sorted(completed, key=lambda r: r.get("seq", 0))
        completed_stage_sequence = [r.get("stage") for r in completed_sorted]
        expected_sequence = [s.value for s in FULL_CHAIN_ORDER]
        # Discriminator (Closure Obligations, SILENCE/ABSENCE): the full
        # chain is only genuinely "traceable back to intake" if a REAL
        # PipelineStageStarted(rca) record exists for this defect_id --
        # i.e. `queue_item_count == 1` -- not merely because every stage
        # was subsequently completed. Without this guard, driving the
        # SIBLING pipeline's remaining stages directly (this method's own
        # job) would satisfy "full chain complete" even while the RED
        # `consolidation-signal-tick` scaffold writes NOTHING, the exact
        # vacuous-pass this slice's own negative-oracle discipline forbids.
        full_chain_traceable = (
            scope_defect_id is not None
            and queue_item_count == 1
            and completed_stage_sequence == expected_sequence
        )
        slice_commit_verified_present = (
            PipelineStage.COMMIT_SLICE.value in completed_stage_sequence
        )

        rejected_records = [r for r in up_to_sample if r.get("event") == _REJECTED]
        intake_rejected = bool(rejected_records)
        rejection_reason_named = intake_rejected and all(
            bool(r.get("reason")) for r in rejected_records
        )

        return IntakeOutcome(
            queue_item_count=queue_item_count,
            traceable_to_signal=traceable_to_signal,
            full_chain_traceable=full_chain_traceable,
            slice_commit_verified_present=slice_commit_verified_present,
            intake_rejected=intake_rejected,
            rejection_reason_named=rejection_reason_named,
        )


@pytest.fixture
def intake_fixture(tmp_path) -> ConsolidationIntakeFixture:
    """The single composition-root service all slice-04 step methods delegate to."""
    return ConsolidationIntakeFixture(tmp_path)


@pytest.fixture
def state_04() -> dict:
    """Per-scenario scratchpad: `outcome`."""
    return {}


__all__ = [
    "ConsolidationIntakeFixture",
]
