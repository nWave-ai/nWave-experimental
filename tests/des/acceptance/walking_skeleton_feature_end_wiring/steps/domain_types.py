"""Domain types for the fix-walking-skeleton-feature-end-wiring slice.

Mandate-12 criterion 1 (ATDD SSOT via Types + Services + DSL): every domain
noun used in the Gherkin is expressed once here as a typed enum / NewType.
Step bodies and the composition service consume these typed parameters -- no
raw ``str`` where a domain enum exists.

CONTRACT SOURCE: the SSOT for "feature is closeable" is the
``_REQUIRED_FEATURE_END_RECORDS`` frozenset at
``src/des/adapters/drivers/hooks/subagent_stop_handler.py:754-760``. This
slice extends it to 4 records by including ``WalkingSkeletonGateRan`` and
extends the union read to include ``walking_skeleton_events()``. The CLI
mirror at ``src/des/cli/verify_deliver_integrity.py:329-336`` carries the
same extension so the CLI verdict matches the hook block.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "fix-walking-skeleton-feature-end-wiring").
FeatureId = NewType("FeatureId", str)


class FeatureEndLedgerState(str, Enum):
    """The two ledger states the U4 enforcer sweep observes.

    Each state describes which records the per-scenario tmp ledger holds at
    the moment the U4 enforcer / verify_deliver_integrity CLI reads it.

    COMPLETE_WITH_WALKING_SKELETON  -- the four required heartbeats are all
        present (``EBatchRefactorCompleted``, ``EnvironmentalE2eGateRan``,
        ``FeatureEndReviewVerdict``, ``WalkingSkeletonGateRan``); the U4
        enforcer returns an EMPTY missing-record set.
    COMPLETE_WITHOUT_WALKING_SKELETON -- the three pre-extension required
        records are present (refactor, env-e2e heartbeat, review verdict) but
        the new walking-skeleton heartbeat is ABSENT; the U4 enforcer returns
        a missing-record set containing ``WalkingSkeletonGateRan``.
    """

    COMPLETE_WITH_WALKING_SKELETON = "complete with the walking-skeleton heartbeat"
    COMPLETE_WITHOUT_WALKING_SKELETON = (
        "complete without the walking-skeleton heartbeat"
    )


class MissingRecordOutcome(str, Enum):
    """Whether the walking-skeleton heartbeat appears in the U4 missing set.

    The single port-exposed observable is the missing-record set returned by
    ``_missing_feature_end_cycle_records``. ``ABSENT`` means the heartbeat is
    NOT in the missing set (i.e. it was recorded on the ledger); ``PRESENT``
    means the heartbeat IS in the missing set (i.e. its absence from the
    ledger was detected by the enforcer).
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

MISSING_OUTCOME_BY_PHRASE: dict[str, MissingRecordOutcome] = {
    o.value: o for o in MissingRecordOutcome
}
