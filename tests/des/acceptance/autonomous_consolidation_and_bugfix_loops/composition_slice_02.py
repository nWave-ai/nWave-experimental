"""Composition root + shared fixtures for autonomous-consolidation-and-bugfix-loops
slice-02 (an exhausted loop stops instead of idle-holding — charter
`an-exhausted-loop-stops-instead-of-idle-holding.md`, feature-delta Slice Plan
row slice-02, Locked Decision D-2).

Pillar 3 (App as in production): the SUT is the REAL
``des work-exhausted-tick`` CLI entry (``des.cli.work_exhausted_tick.main``),
driven IN-PROCESS once per tick via the SAME reusable in-process driving-port
helper the shipped corpus already uses (``run_cli_in_process`` —
``tests/common/in_process_cli.py``). This module NEVER imports the
not-yet-created domain ladder-evaluation seam (``des.domain.
work_exhausted_ladder``) — only the real CLI entry point is driven.
``AtCompletionLedger`` is imported ONLY to OBSERVE the resulting records (the
S2 tolerable-variant, same as the ``oss-spine-watchdog`` / slice-01
siblings) — it is substrate observation, NOT the SUT.

── THE CONTROLLABLE CLOCK (deterministic ladder, NO real sleep) ──
Every tick supplies an explicit ``--now`` instant computed from a FIXED base
timestamp plus a caller-chosen minute offset — the exact mechanism the
charter demands ("inject a clock so the AT is deterministic and fast, never
real sleeps"). A multi-tick sequence models an operator walking away for the
full ladder without a single real-time wait.

── THE DISTILL-INTERIM QUEUE MODEL (feature-delta Open Question 2) ──
No DESIGN wave ran; the "safe-work tier" queue model is resolved HERE — see
``steps.domain_types_slice_02`` module docstring for the full contract. In
short: a 4-way ``QueueState`` (empty / all-gated / has-unblocked-item /
malformed); the first three are exhausted, only ``has-unblocked-item`` is a
fresh trigger.

── Mechanical assertion (Mandate-13 invariant 5) ──
Python + filesystem only (the CLI resolves a real project root + reads/would-
write a real ledger JSONL, as in production), cross-OS. No git subprocess is
needed for this slice (unlike slice-01) — the ladder has no transcript to
read, only the ledger + the injected clock.

Universe (Mandate 8): {outcome.first_warning_fired,
outcome.first_warning_within_ceiling, outcome.second_warning_fired,
outcome.second_warning_within_ceiling, outcome.stop_escalate_fired,
outcome.stop_escalate_within_ceiling, outcome.reason_named,
outcome.window_resolved, outcome.resumed_without_fresh_trigger,
outcome.new_record_count, outcome.ledger_proves_ladder_from_timestamps_alone}.
Internal fields (Popen handle, argv list, raw ledger path) NEVER appear.

Layer 3/4 (real filesystem + real ledger JSONL + real CLI invocation against
tmp_path): example-only (Mandate 9 v2 — the driven set includes a real
filesystem adapter + a real in-process CLI invocation => @real-io =>
example-based, NOT PBT). Sad paths explicit (Mandate 11); density comes from
Scenario Outline ``Examples:`` tables over the time-ladder + resolution-
timing + tick-cadence space instead. No PBT machinery imported.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Observation-only substrate reader (NOT the SUT). Reads back the appended
# records — the S2 tolerable-variant, same as the oss-spine-watchdog /
# slice-01 siblings.
from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger

# The REAL `des work-exhausted-tick` CLI entry, driven IN-PROCESS via the
# shared reusable driving-port helper (node-C enabler `run_cli_in_process`) —
# the same faithful in-process pattern the shipped corpus already migrated
# to (post `corpus-migration-in-process`).
from des.cli.work_exhausted_tick import main as _work_exhausted_tick_main
from tests.common.in_process_cli import run_cli_in_process

from .steps.domain_types_slice_02 import (
    FIRST_WARNING_MINUTES,
    SECOND_WARNING_MINUTES,
    STOP_ESCALATE_MINUTES,
    EscalationOutcome,
    FeatureId,
    QueueState,
)


# The feature this suite builds a synthetic loop-tick sequence for. Distinct
# from the carpaccio `@slice-02` tag on the .feature scenarios themselves
# (that tag names THIS AT's own carpaccio slice; this constant is an
# arbitrary fixture key inside the fake ledger namespace, mirroring
# slice-01's `-demo` disambiguation).
_FEATURE_ID = FeatureId("autonomous-consolidation-and-bugfix-loops-demo-slice02")

# The controllable-clock base instant every tick's minute offset is computed
# from. Arbitrary and fixed — the point is determinism, not calendar realism.
_BASE_INSTANT = datetime(2026, 6, 1, 9, 0, 0, tzinfo=timezone.utc)

_LADDER_EVENTS = frozenset(
    {
        "WorkExhaustedWindowOpened",
        "WorkExhaustedFirstWarning",
        "WorkExhaustedSecondWarning",
        "WorkExhaustedStopEscalate",
        "WorkExhaustedWindowResolved",
    }
)


def _at_minute(offset_minutes: float) -> str:
    """An ISO-8601 instant `offset_minutes` after the fixed base — the
    controllable clock. Pure function, no real sleep.
    """
    moment = _BASE_INSTANT + timedelta(minutes=offset_minutes)
    return moment.isoformat().replace("+00:00", "Z")


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass
class EscalationFixture:
    """Composition-root service for autonomous-consolidation-and-bugfix-loops
    slice-02 ATs.

    Pillar 3: fires one or more REAL ``des work-exhausted-tick`` CLI ticks
    in-process against a synthetic controllable-clock timeline, then
    interprets the AT-completion ledger's OWN recorded content into the
    port-exposed ``EscalationOutcome`` — never re-simulating the ladder logic
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

    # --- driving-port invocation (the REAL CLI, one tick at a time) --------

    def _fire_one_tick(
        self,
        *,
        queue_state: QueueState,
        at_minute: float,
        gated_reasons: str | None,
    ) -> None:
        """Fire the REAL ``des work-exhausted-tick`` entry once, in-process."""
        argv = [
            "--feature-id",
            str(_FEATURE_ID),
            "--project-root",
            str(self._repo),
            "--queue-state",
            queue_state.value,
            "--now",
            _at_minute(at_minute),
        ]
        if gated_reasons is not None:
            argv += ["--gated-reasons", gated_reasons]
        run_cli_in_process(argv, cwd=self._repo, main=_work_exhausted_tick_main)

    def run_ladder_sequence(
        self,
        ticks: list[tuple[QueueState, float]],
        *,
        gated_reasons: str | None = None,
    ) -> EscalationOutcome:
        """Fire a whole SEQUENCE of ticks (the operator walking away across
        the ladder), then interpret the ledger's cumulative content.

        ``ticks`` is an ordered ``(queue_state, at_minute)`` list — the
        controllable-clock timeline this scenario walks. No real sleep
        between ticks.
        """
        for queue_state, at_minute in ticks:
            self._fire_one_tick(
                queue_state=queue_state,
                at_minute=at_minute,
                gated_reasons=gated_reasons,
            )
        return self._interpret(self._read_all())

    def fire_additional_tick(
        self,
        *,
        queue_state: QueueState,
        at_minute: float,
        gated_reasons: str | None = None,
    ) -> EscalationOutcome:
        """Fire ONE more tick against whatever ledger state already exists,
        and return the outcome interpreted from the FULL post-tick ledger —
        with ``new_record_count`` scoped to just THIS tick's delta (the
        re-arm / no-quiet-un-stop shape, mirroring slice-01 AT-04).
        """
        before = self._read_all()
        self._fire_one_tick(
            queue_state=queue_state, at_minute=at_minute, gated_reasons=gated_reasons
        )
        after = self._read_all()
        outcome = self._interpret(after)
        return EscalationOutcome(
            first_warning_fired=outcome.first_warning_fired,
            first_warning_within_ceiling=outcome.first_warning_within_ceiling,
            second_warning_fired=outcome.second_warning_fired,
            second_warning_within_ceiling=outcome.second_warning_within_ceiling,
            stop_escalate_fired=outcome.stop_escalate_fired,
            stop_escalate_within_ceiling=outcome.stop_escalate_within_ceiling,
            reason_named=outcome.reason_named,
            window_resolved=outcome.window_resolved,
            resumed_without_fresh_trigger=outcome.resumed_without_fresh_trigger,
            new_record_count=len(after) - len(before),
            ledger_proves_ladder_from_timestamps_alone=(
                outcome.ledger_proves_ladder_from_timestamps_alone
            ),
        )

    # --- scenario-shaped sequence builders (Mandate-12 criterion 3: the CSV/
    # cadence/resolve arithmetic lives HERE, never in a step body) -----------

    def tick_in_turn(
        self,
        queue_state: QueueState,
        open_at_minute: float,
        minutes_csv: str,
        *,
        gated_reasons: str | None = None,
    ) -> EscalationOutcome:
        """Open the window at ``open_at_minute``, then tick in turn at each
        comma-separated minute in ``minutes_csv`` — one tick per ratified
        checkpoint, mirroring a loop that ticks roughly as often as the
        ladder itself moves (AT-05's per-threshold precision check).
        """
        checkpoints = [float(m) for m in minutes_csv.split(",")]
        ticks = [(queue_state, open_at_minute)] + [
            (queue_state, m) for m in checkpoints
        ]
        return self.run_ladder_sequence(ticks, gated_reasons=gated_reasons)

    def tick_at_cadence_until(
        self,
        queue_state: QueueState,
        open_at_minute: float,
        cadence_minutes: float,
        until_minute: float,
        *,
        gated_reasons: str | None = None,
    ) -> EscalationOutcome:
        """Open the window at ``open_at_minute``, then tick every
        ``cadence_minutes`` until ``until_minute`` is reached (AT-06's
        cadence-invariance check — the SAME wall-clock ceiling must hold
        whether the loop ticks every 5 minutes or jumps straight to the end
        in ONE tick).
        """
        minutes = [open_at_minute]
        cursor = open_at_minute
        while cursor < until_minute:
            cursor = min(cursor + cadence_minutes, until_minute)
            minutes.append(cursor)
        if minutes[-1] != until_minute:
            minutes.append(until_minute)
        ticks = [(queue_state, m) for m in minutes]
        return self.run_ladder_sequence(ticks, gated_reasons=gated_reasons)

    def resolve_after(
        self,
        queue_state: QueueState,
        open_at_minute: float,
        first_check_minute: float,
        second_check_minute: float,
        resolve_at_minute: float,
        *,
        gated_reasons: str | None = None,
    ) -> EscalationOutcome:
        """Open the window, ride it through two ladder checkpoints, then a
        freshly-unblocked item arrives at ``resolve_at_minute`` (AT-08's
        "resolves before the ceiling" shape — mirrors feature-delta Domain
        Example 2: gated at 09:00, warnings at 09:20/09:30, resolved 09:38).
        """
        ticks = [
            (queue_state, open_at_minute),
            (queue_state, first_check_minute),
            (queue_state, second_check_minute),
            (QueueState.HAS_UNBLOCKED_ITEM, resolve_at_minute),
        ]
        return self.run_ladder_sequence(ticks, gated_reasons=gated_reasons)

    def escalate_to_stop(
        self,
        queue_state: QueueState,
        open_at_minute: float,
        escalate_by_minute: float,
        *,
        gated_reasons: str | None = None,
    ) -> EscalationOutcome:
        """Precondition setup (Given): ride a window through the full ladder
        to STOP/ESCALATE — arms the "already stopped" precondition AT-10
        checks a re-tick against. Returns the outcome (NOT discarded): the
        Then step asserts `stop_escalate_fired` genuinely held BEFORE
        trusting the re-tick's zero-new-records as meaningful — the
        looked-and-genuinely-absent vs never-actually-looked discriminator
        (Closure Obligations, SILENCE/ABSENCE). Without this discriminator a
        scaffold that writes NOTHING at all would pass AT-10 vacuously.
        """
        return self.run_ladder_sequence(
            [
                (queue_state, open_at_minute),
                (queue_state, FIRST_WARNING_MINUTES),
                (queue_state, SECOND_WARNING_MINUTES),
                (queue_state, escalate_by_minute),
            ],
            gated_reasons=gated_reasons,
        )

    # --- ledger observation --------------------------------------------------

    def _read_all(self) -> list[dict]:
        """Read every record for this fixture's ledger (port read, port-exposed)."""
        ledger = AtCompletionLedger(_FEATURE_ID, self._repo)
        try:
            return ledger.read_records()
        except Exception:
            return []

    def _interpret(self, records: list[dict]) -> EscalationOutcome:
        """Build the port-exposed observable outcome from the ledger's OWN
        recorded content — never from the fixture's own tick-scheduling
        bookkeeping. This is the observer half of the D-8 no-orphan /
        negative-oracle discipline: the outcome is what the ledger actually
        proves, not what the test expected to have happened.
        """
        ladder_records = [r for r in records if r.get("event") in _LADDER_EVENTS]
        by_event = {}
        for record in ladder_records:
            by_event.setdefault(record["event"], []).append(record)

        def _fired(event: str) -> dict | None:
            rows = by_event.get(event)
            return rows[-1] if rows else None

        opened = _fired("WorkExhaustedWindowOpened")
        first = _fired("WorkExhaustedFirstWarning")
        second = _fired("WorkExhaustedSecondWarning")
        stop = _fired("WorkExhaustedStopEscalate")
        resolved = _fired("WorkExhaustedWindowResolved")

        def _within(record: dict | None, ceiling: int) -> bool:
            if record is None:
                return False
            gap = record.get("gap_minutes")
            return isinstance(gap, (int, float)) and gap <= ceiling

        fired_ladder = [r for r in (first, second, stop) if r is not None]
        reason_named = bool(fired_ladder) and all(
            bool(r.get("reason")) for r in fired_ladder
        )

        # resumed_without_fresh_trigger: any record with a HIGHER seq than
        # the first STOP/ESCALATE record, other than a WorkExhaustedWindowResolved
        # (the one legitimate fresh-trigger record) — a ledger-content-only
        # check, never a re-simulation of the ladder logic.
        resumed = False
        if stop is not None:
            stop_seq = stop.get("seq")
            resumed = any(
                r.get("seq") is not None
                and stop_seq is not None
                and r["seq"] > stop_seq
                and r.get("event") != "WorkExhaustedWindowResolved"
                for r in ladder_records
            )

        # ledger_proves_ladder_from_timestamps_alone: the charter's own
        # negative-oracle definition, computed strictly from ledger
        # timestamps — no window opened => vacuously proven; a window opened
        # and closed (STOP or resolved) within 45 minutes => proven; a still-
        # open window is checked against the LATEST timestamp the ledger
        # itself carries (the "or to now if still open" clause).
        proves_from_timestamps = True
        if opened is not None and isinstance(opened.get("timestamp"), str):
            t_open = _parse_ts(opened["timestamp"])
            if stop is not None and isinstance(stop.get("timestamp"), str):
                gap = (_parse_ts(stop["timestamp"]) - t_open).total_seconds() / 60.0
                proves_from_timestamps = gap <= STOP_ESCALATE_MINUTES
            else:
                timestamps = [
                    _parse_ts(r["timestamp"])
                    for r in records
                    if isinstance(r.get("timestamp"), str)
                ]
                latest_known = max(timestamps) if timestamps else t_open
                gap = (latest_known - t_open).total_seconds() / 60.0
                proves_from_timestamps = gap <= STOP_ESCALATE_MINUTES

        return EscalationOutcome(
            first_warning_fired=first is not None,
            first_warning_within_ceiling=_within(first, FIRST_WARNING_MINUTES),
            second_warning_fired=second is not None,
            second_warning_within_ceiling=_within(second, SECOND_WARNING_MINUTES),
            stop_escalate_fired=stop is not None,
            stop_escalate_within_ceiling=_within(stop, STOP_ESCALATE_MINUTES),
            reason_named=reason_named,
            window_resolved=resolved is not None and stop is None,
            resumed_without_fresh_trigger=resumed,
            new_record_count=len(records),
            ledger_proves_ladder_from_timestamps_alone=proves_from_timestamps,
        )


@pytest.fixture
def escalation_fixture(tmp_path) -> EscalationFixture:
    """The single composition-root service all slice-02 step methods delegate to."""
    return EscalationFixture(tmp_path)


@pytest.fixture
def state_02() -> dict:
    """Per-scenario scratchpad: `ticks`, `outcome`, `before`."""
    return {}


__all__ = [
    "EscalationFixture",
]
