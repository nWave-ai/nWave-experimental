"""Domain types for the fix-distill-signoff-feature-end-wiring slice.

Mandate-12 criterion 1 (ATDD SSOT via Types + Services + DSL): every domain
noun used in the Gherkin is expressed once here as a typed enum / NewType.
Step bodies and the composition service consume these typed parameters -- no
raw ``str`` where a domain enum exists.

CONTRACT SOURCE: the SSOT for "feature is closeable" is the
``_REQUIRED_FEATURE_END_RECORDS`` frozenset at
``src/des/adapters/drivers/hooks/subagent_stop_handler.py:758-765``. This
slice extends it to 6 records by including
``CoverageMapVerifiedAtDistillExit`` and ``CoverageMapVerifiedAtDeliverExit``
and extends the union read to include ``coverage_map_touchpoint_events()``.
The CLI mirror at ``src/des/cli/verify_deliver_integrity.py:332-344``
carries the same extension so the CLI verdict matches the hook block.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "fix-distill-signoff-feature-end-wiring").
FeatureId = NewType("FeatureId", str)


class FeatureEndLedgerState(str, Enum):
    """The three ledger states the U4 enforcer sweep observes.

    Each state describes which records the per-scenario tmp ledger holds at
    the moment the U4 enforcer / verify_deliver_integrity CLI reads it.

    COMPLETE_WITH_BOTH_COVERAGE_MAP -- the six required heartbeats are all
        present (``EBatchRefactorCompleted``, ``EnvironmentalE2eGateRan``,
        ``FeatureEndReviewVerdict``, ``WalkingSkeletonGateRan``,
        ``CoverageMapVerifiedAtDistillExit``,
        ``CoverageMapVerifiedAtDeliverExit``); the U4 enforcer returns an
        EMPTY missing-record set.
    COMPLETE_WITHOUT_DISTILL_EXIT -- five of six required records present;
        the ``CoverageMapVerifiedAtDistillExit`` heartbeat is ABSENT; the
        U4 enforcer returns a missing-record set containing the distill-exit
        heartbeat (and ONLY that one).
    COMPLETE_WITHOUT_DELIVER_EXIT -- five of six required records present;
        the ``CoverageMapVerifiedAtDeliverExit`` heartbeat is ABSENT; the
        U4 enforcer returns a missing-record set containing the deliver-exit
        heartbeat (and ONLY that one).
    """

    COMPLETE_WITH_BOTH_COVERAGE_MAP = "complete with both coverage-map heartbeats"
    COMPLETE_WITHOUT_DISTILL_EXIT = (
        "complete without the coverage-map distill-exit heartbeat"
    )
    COMPLETE_WITHOUT_DELIVER_EXIT = (
        "complete without the coverage-map deliver-exit heartbeat"
    )


class CoverageMapTouchpoint(str, Enum):
    """Which of the two coverage-map touchpoints the assertion observes.

    DISTILL_EXIT -- the ``CoverageMapVerifiedAtDistillExit`` heartbeat
        (emitted by ``verify_coverage_map verify --touchpoint distill_exit``
        on a passing verdict; consumed at the DISTILL-to-DELIVER handoff).
    DELIVER_EXIT -- the ``CoverageMapVerifiedAtDeliverExit`` heartbeat
        (emitted by ``verify_coverage_map verify --touchpoint deliver_exit``
        on a passing verdict; consumed at feature-end re-check).
    """

    DISTILL_EXIT = "distill-exit"
    DELIVER_EXIT = "deliver-exit"

    @property
    def record_name(self) -> str:
        """The ledger event-name constant for this touchpoint."""
        return {
            CoverageMapTouchpoint.DISTILL_EXIT: "CoverageMapVerifiedAtDistillExit",
            CoverageMapTouchpoint.DELIVER_EXIT: "CoverageMapVerifiedAtDeliverExit",
        }[self]


class MissingRecordOutcome(str, Enum):
    """Whether the named touchpoint heartbeat appears in the U4 missing set.

    The single port-exposed observable is the missing-record set returned by
    ``_missing_feature_end_cycle_records``. ``ABSENT`` means the heartbeat
    is NOT in the missing set (i.e. it was recorded on the ledger);
    ``PRESENT`` means the heartbeat IS in the missing set (i.e. its absence
    from the ledger was detected by the enforcer).
    """

    ABSENT = "absent"
    PRESENT = "present"


# --- Phrase -> typed-value lookup tables -------------------------------------
# Mandate-12 criterion 3: the DSL emerges from typed concepts. Each Gherkin
# literal maps to a typed enum here; the parameterized step templates in
# `common_steps.py` do a single dict lookup, never an `if`-ladder.

LEDGER_STATE_BY_PHRASE: dict[str, FeatureEndLedgerState] = {
    s.value: s for s in FeatureEndLedgerState
}

TOUCHPOINT_BY_PHRASE: dict[str, CoverageMapTouchpoint] = {
    t.value: t for t in CoverageMapTouchpoint
}

MISSING_OUTCOME_BY_PHRASE: dict[str, MissingRecordOutcome] = {
    o.value: o for o in MissingRecordOutcome
}
