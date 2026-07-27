"""des.domain.work_exhausted_ladder -- the wall-clock work-exhausted escalation
ladder (D-2).

autonomous-consolidation-and-bugfix-loops slice-02 (charter
`an-exhausted-loop-stops-instead-of-idle-holding.md`, feature-delta Slice
Plan row slice-02). This is the DELIVER seam `des.cli.work_exhausted_tick`
lazily imported while it did not exist -- the RED scaffold's own
DELIVER-pinned assumption:

    evaluate_and_record(*, ledger, feature_id, queue_state, now,
                         gated_reasons) -> None

── The ratified wall-clock ladder (D-2, verbatim) ──
20 minutes -> FIRST WARNING, 30 minutes -> SECOND WARNING, 45 minutes ->
STOP/ESCALATE (hard ceiling). Anchored to minutes-since-first-detected-
exhausted, never to a tick count -- the SAME ceiling holds whether the loop
ticks every 5 minutes, every 23 minutes, or jumps straight from 0 to 46 in
ONE tick.

── The DISTILL-interim queue model (feature-delta Open Question 2) ──
The safe-work tier a tick observes is exactly a 4-way `--queue-state`:
`empty` / `all-gated` / `has-unblocked-item` / `malformed`. The first three
are EXHAUSTED (`malformed` is deliberately treated as exhausted -- SAFE,
never an indeterminate hang). Only `has-unblocked-item` is a fresh
triggering condition -- the ONLY state that resolves an open window and the
ONLY state that can resume a loop past its own STOP/ESCALATE.

── Timestamp-anchored ladder records (the D-2/D-8 negative-oracle mechanism) ──
Every rung record (`WorkExhaustedFirstWarning` / `WorkExhaustedSecondWarning`
/ `WorkExhaustedStopEscalate`) is written with its `timestamp` set to the
THEORETICAL ratified-threshold crossing instant -- `window_open_ts +
threshold_minutes` -- never the tick's own wall-clock `now`. A sparse-cadence
tick may only DISCOVER a crossing late (e.g. a single tick jumping from
minute 0 to minute 50), but the record it writes proves the crossing
happened AT its ratified minute, not at the tick that noticed it. This is
the mechanism that makes the ledger alone provable "no exhausted window ran
past 45 minutes without a STOP/ESCALATE record" purely from its own
recorded timestamps (D-8 no-orphan / negative-oracle discipline), regardless
of how the loop happens to tick.

── No quiet un-stop (D-2 negative) ──
Once a window's `WorkExhaustedStopEscalate` has fired, that window is
TERMINAL: a further exhausted tick against it appends NOTHING. Only a
`has-unblocked-item` tick resolves it (`WorkExhaustedWindowResolved`,
timestamped at the REAL tick `now` -- a genuine resolve event, not a
retroactive threshold crossing) and clears the terminal state so a LATER
exhausted tick can open a brand-new window.

Reference: docs/feature/autonomous-consolidation-and-bugfix-loops/
           feature-delta.md, slice-02 (## Wave: DISTILL / [REF]
           Wave-Decision Reconciliation, OQ-2 resolution).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from des.domain.iso_utc import format_iso_utc, parse_iso_utc


if TYPE_CHECKING:
    from des.ports.driven_ports.at_completion_ledger_port import AtCompletionLedgerPort


# The ratified wall-clock ladder thresholds (D-2), in minutes since the
# exhausted-state window was first detected.
FIRST_WARNING_MINUTES = 20
SECOND_WARNING_MINUTES = 30
STOP_ESCALATE_MINUTES = 45

# The ladder's event vocabulary -- the DELIVER-pinned record kinds.
WINDOW_OPENED = "WorkExhaustedWindowOpened"
FIRST_WARNING = "WorkExhaustedFirstWarning"
SECOND_WARNING = "WorkExhaustedSecondWarning"
STOP_ESCALATE = "WorkExhaustedStopEscalate"
WINDOW_RESOLVED = "WorkExhaustedWindowResolved"

_LADDER_EVENTS = frozenset(
    {WINDOW_OPENED, FIRST_WARNING, SECOND_WARNING, STOP_ESCALATE, WINDOW_RESOLVED}
)

# The OQ-2-resolved 4-way queue-state vocabulary's ONE fresh-triggering value
# -- every other value (`empty` / `all-gated` / `malformed`) is exhausted.
_FRESH_TRIGGER_STATE = "has-unblocked-item"


def _reason(queue_state: str, gated_reasons: str | None) -> str:
    """WHY this tick's ladder decision fired -- charter Positive-2: "each
    record names WHY". Never empty.
    """
    if gated_reasons:
        return f"queue_state={queue_state}; gated_reasons={gated_reasons}"
    return f"queue_state={queue_state}"


@dataclass
class _OpenWindow:
    """The replayed state of the LATEST still-open (or terminal) window."""

    open_ts: datetime
    first_fired: bool = False
    second_fired: bool = False
    stop_fired: bool = False


def _current_window(ladder_records: list[dict[str, Any]]) -> _OpenWindow | None:
    """Replay the ladder's OWN recorded content, in append order, to find the
    state of the window currently open (if any) -- never re-derived from
    anything but the ledger itself (D-8 no-orphan discipline).
    """
    window: _OpenWindow | None = None
    for record in ladder_records:
        event = record.get("event")
        if event == WINDOW_OPENED:
            timestamp = record.get("timestamp")
            window = (
                _OpenWindow(open_ts=parse_iso_utc(timestamp))
                if isinstance(timestamp, str)
                else None
            )
        elif window is None:
            continue
        elif event == FIRST_WARNING:
            window.first_fired = True
        elif event == SECOND_WARNING:
            window.second_fired = True
        elif event == STOP_ESCALATE:
            window.stop_fired = True
        elif event == WINDOW_RESOLVED:
            window = None
    return window


def evaluate_and_record(
    *,
    ledger: AtCompletionLedgerPort,
    feature_id: str,
    queue_state: str,
    now: datetime,
    gated_reasons: str | None,
) -> None:
    """Evaluate one work-exhausted tick against the ratified 20/30/45-minute
    wall-clock escalation ladder (D-2) and append whichever ladder record it
    newly crosses at ``now`` -- the window state is replayed from the
    ledger's own recorded content only, never from caller-side bookkeeping
    (D-8 no-orphan discipline).
    """
    ladder_records = [
        record
        for record in ledger.read_records(feature_id=feature_id)
        if record.get("event") in _LADDER_EVENTS
    ]
    window = _current_window(ladder_records)
    reason = _reason(queue_state, gated_reasons)

    if queue_state == _FRESH_TRIGGER_STATE:
        if window is not None:
            gap_minutes = (now - window.open_ts).total_seconds() / 60.0
            ledger.append_work_exhausted_event(
                WINDOW_RESOLVED,
                timestamp=format_iso_utc(now),
                gap_minutes=gap_minutes,
                reason=reason,
                feature_id=feature_id,
            )
        return

    if window is None:
        ledger.append_work_exhausted_event(
            WINDOW_OPENED,
            timestamp=format_iso_utc(now),
            gap_minutes=0,
            reason=reason,
            feature_id=feature_id,
        )
        return

    if window.stop_fired:
        # Terminal window -- "no quiet un-stop" (D-2 negative). A further
        # exhausted tick appends NOTHING until a fresh trigger resolves it.
        return

    elapsed_minutes = (now - window.open_ts).total_seconds() / 60.0

    if elapsed_minutes >= FIRST_WARNING_MINUTES and not window.first_fired:
        ledger.append_work_exhausted_event(
            FIRST_WARNING,
            timestamp=format_iso_utc(
                window.open_ts + timedelta(minutes=FIRST_WARNING_MINUTES)
            ),
            gap_minutes=FIRST_WARNING_MINUTES,
            reason=reason,
            feature_id=feature_id,
        )
    if elapsed_minutes >= SECOND_WARNING_MINUTES and not window.second_fired:
        ledger.append_work_exhausted_event(
            SECOND_WARNING,
            timestamp=format_iso_utc(
                window.open_ts + timedelta(minutes=SECOND_WARNING_MINUTES)
            ),
            gap_minutes=SECOND_WARNING_MINUTES,
            reason=reason,
            feature_id=feature_id,
        )
    if elapsed_minutes >= STOP_ESCALATE_MINUTES and not window.stop_fired:
        ledger.append_work_exhausted_event(
            STOP_ESCALATE,
            timestamp=format_iso_utc(
                window.open_ts + timedelta(minutes=STOP_ESCALATE_MINUTES)
            ),
            gap_minutes=STOP_ESCALATE_MINUTES,
            reason=reason,
            feature_id=feature_id,
        )


__all__ = [
    "FIRST_WARNING_MINUTES",
    "SECOND_WARNING_MINUTES",
    "STOP_ESCALATE_MINUTES",
    "evaluate_and_record",
]
