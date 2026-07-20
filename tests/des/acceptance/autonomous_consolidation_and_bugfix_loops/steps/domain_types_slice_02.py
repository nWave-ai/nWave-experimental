"""Domain types for autonomous-consolidation-and-bugfix-loops slice-02
(an exhausted loop stops instead of idle-holding, charter
`an-exhausted-loop-stops-instead-of-idle-holding.md`).

Mandate-12 criterion 1 (SSOT via Types + Services + DSL): every domain noun
the slice-02 ``.feature`` scenarios speak lives here as a typed enum or frozen
dataclass. Step methods + composition consume these typed parameters; raw
``str`` parameters are avoided wherever a domain enum exists.

── DISTILL-interim decision (feature-delta Open Question 2, no DESIGN wave ran
for this feature) -- "the safe-work tier" queue model ──
``QueueState`` below IS the concrete, testable resolution: a 4-way state --
``EMPTY`` / ``ALL_GATED`` / ``HAS_UNBLOCKED_ITEM`` / ``MALFORMED``. The first
three are "exhausted" (``MALFORMED`` -- an ambiguous/corrupted queue read --
is deliberately treated as exhausted, i.e. SAFE, never as an indeterminate
hang the charter's "What to explore" section warns against). Only
``HAS_UNBLOCKED_ITEM`` is a fresh triggering condition: it both resolves an
open exhausted-state window AND is the ONLY state that can resume a loop
past its own STOP/ESCALATE (the "no quiet un-stop" guarantee). Full contract:
``src/des/cli/work_exhausted_tick.py`` module docstring.

── The ratified wall-clock ladder (D-2, verbatim) ──
20 minutes -> FIRST WARNING, 30 minutes -> SECOND WARNING, 45 minutes ->
STOP/ESCALATE (hard ceiling). Anchored to minutes-since-first-detected-
exhausted, never to a tick count.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NewType


# A kebab-case feature identifier.
FeatureId = NewType("FeatureId", str)

# The ratified wall-clock ladder thresholds (D-2), in minutes since the
# exhausted-state window was first detected. SSOT for both the fixture's
# tick-scheduling and the observer-side invariant check below.
FIRST_WARNING_MINUTES = 20
SECOND_WARNING_MINUTES = 30
STOP_ESCALATE_MINUTES = 45


class QueueState(str, Enum):
    """The 4-way safe-work-tier state a loop tick observes (OQ-2 resolution).

    Each value is the CLI's ``--queue-state`` wire value AND the Gherkin
    phrase the ``.feature`` file speaks -- Mandate-12 DSL emergence (one
    typed vocabulary, no separate business-phrase-to-enum table needed
    because the enum value already IS the readable phrase).
    """

    EMPTY = "empty"
    ALL_GATED = "all-gated"
    HAS_UNBLOCKED_ITEM = "has-unblocked-item"
    MALFORMED = "malformed"

    @property
    def is_exhausted(self) -> bool:
        """True for every state EXCEPT the one fresh triggering condition."""
        return self is not QueueState.HAS_UNBLOCKED_ITEM


class LadderRung(str, Enum):
    """One rung of the ratified 20/30/45-minute escalation ladder."""

    FIRST_WARNING = "FIRST WARNING"
    SECOND_WARNING = "SECOND WARNING"
    STOP_ESCALATE = "STOP/ESCALATE"


@dataclass(frozen=True)
class EscalationOutcome:
    """Observable outcome of a SEQUENCE of work-exhausted ticks (Layer 3/4).

    The driving port is the real ``des work-exhausted-tick`` CLI entry
    (``des.cli.work_exhausted_tick.main``), driven IN-PROCESS once per tick.
    Universe entries ``assert_state_delta`` tracks are built from THIS
    dataclass's port-exposed fields ONLY -- never a Popen handle, an argv
    list, or the raw ledger file path (Mandate 8).

    - `first_warning_fired`          -- True iff a FIRST WARNING record was
                                         appended for the (single) exhausted
                                         window this outcome observes.
    - `first_warning_within_ceiling` -- True iff that record's
                                         minutes-since-first-detected gap was
                                         <= 20 (the ratified ceiling, not a
                                         bare presence check).
    - `second_warning_fired`         -- as above, for SECOND WARNING.
    - `second_warning_within_ceiling`-- gap <= 30.
    - `stop_escalate_fired`          -- True iff a STOP/ESCALATE record was
                                         appended.
    - `stop_escalate_within_ceiling` -- gap <= 45.
    - `reason_named`                 -- True iff EVERY fired ladder record
                                         carries a non-empty ``reason`` field
                                         (charter Positive-2: "each record
                                         names WHY").
    - `window_resolved`              -- True iff a
                                         `WorkExhaustedWindowResolved` record
                                         was appended (a fresh
                                         `has-unblocked-item` tick closed the
                                         window) WITHOUT a STOP/ESCALATE ever
                                         having fired for it.
    - `resumed_without_fresh_trigger`-- True iff a NEW ladder/window record
                                         was appended on an exhausted tick
                                         fired AFTER a STOP/ESCALATE record
                                         for the same window already exists
                                         -- the "a stop that quietly un-stops
                                         itself" failure mode the charter
                                         forbids. MUST be False.
    - `new_record_count`             -- total ledger records appended across
                                         every tick this outcome observed.
                                         Used by the no-quiet-un-stop
                                         scenario to assert a POST-STOP
                                         exhausted re-tick appends literally
                                         nothing.
    - `ledger_proves_ladder_from_timestamps_alone` -- True iff an OBSERVER
                                         reading ONLY the ledger's own
                                         recorded timestamps (never the
                                         fixture's tick-scheduling bookkeeping)
                                         can confirm no exhausted-state window
                                         exceeded 45 minutes without a
                                         STOP/ESCALATE record (the charter's
                                         negative-oracle CRITICAL invariant,
                                         AT-07).
    """

    first_warning_fired: bool
    first_warning_within_ceiling: bool
    second_warning_fired: bool
    second_warning_within_ceiling: bool
    stop_escalate_fired: bool
    stop_escalate_within_ceiling: bool
    reason_named: bool
    window_resolved: bool
    resumed_without_fresh_trigger: bool
    new_record_count: int
    ledger_proves_ladder_from_timestamps_alone: bool


# --- Phrase -> typed-value lookup table (Mandate-12 DSL emergence) --------

QUEUE_STATE_BY_PHRASE: dict[str, QueueState] = {q.value: q for q in QueueState}

# The Gherkin GIVEN-phrase vocabulary for an OPENING (exhausted) queue state
# -- deliberately excludes HAS_UNBLOCKED_ITEM, which is never a valid opening
# precondition (it is the one non-exhausted, fresh-trigger state; it only
# ever appears as a later action, never as a starting Given).
QUEUE_STATE_BY_GIVEN_PHRASE: dict[str, QueueState] = {
    "is empty": QueueState.EMPTY,
    "is fully gated": QueueState.ALL_GATED,
    "is ambiguous to parse": QueueState.MALFORMED,
}

# yes/no -> bool lookup table (Mandate-12 DSL emergence) for Scenario Outline
# Examples columns spelled as the readable "yes"/"no" the .feature file uses.
BOOL_BY_YES_NO: dict[str, bool] = {"yes": True, "no": False}


__all__ = [
    "BOOL_BY_YES_NO",
    "FIRST_WARNING_MINUTES",
    "QUEUE_STATE_BY_GIVEN_PHRASE",
    "QUEUE_STATE_BY_PHRASE",
    "SECOND_WARNING_MINUTES",
    "STOP_ESCALATE_MINUTES",
    "EscalationOutcome",
    "FeatureId",
    "LadderRung",
    "QueueState",
]
