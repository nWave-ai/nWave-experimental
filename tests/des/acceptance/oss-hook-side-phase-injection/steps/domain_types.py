"""Domain types for slice-01 -- the G-DISTILL-EXIT SubagentStop gate.

slice-01 of oss-hook-side-phase-injection (the DISTILL-wave hook keystone, D1).
Every domain noun in the slice-01 Gherkin is expressed once here as a typed
enum or NewType; step bodies and the composition service consume these typed
parameters (Mandate-12 criterion 1 -- domain types module exists with typed
enums for every domain noun used in Gherkin).

The G-DISTILL-EXIT gate intercepts an acceptance-designer returning from the
``D_DISTILL`` phase at the SubagentStop boundary. It compares the set of
planned slices (denominator = the feature-delta ``[REF] Slice Plan`` table,
reused from U4's ``_slice_plan_slice_ids``) against the set of slices carrying
a signed ``ATReviewVerdict`` ledger record (numerator). On a complete set it
emits a ``WorkflowPhaseCompletedDistill`` ledger record (the symmetric SUCCESS
terminal, SF ADR-016) and ALLOWS; on an incomplete set it BLOCKS
``DistillExitVerdictIncomplete``; on an absent / unparseable slice-plan table
it BLOCKS ``SlicePlanParseUnresolved`` (fail-closed, never a vacuous pass).

HARD INVARIANT (hook-can't-spawn-agent): the gate only BLOCKS / EMITS -- it
never dispatches the reviewer. The observable surface is the block decision,
the exit code, and the ledger record -- never "the hook dispatched an agent".
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "atdd-pure-demo").
FeatureId = NewType("FeatureId", str)

# A carpaccio slice identifier (e.g. "slice-01").
SliceId = NewType("SliceId", str)


class GateOutcome(str, Enum):
    """The user-observable verdict of the G-DISTILL-EXIT SubagentStop gate.

    ALLOWED -- every planned slice carries a signed verdict; the gate permits
               the DISTILL->DELIVER transition and emits the phase-completed
               success terminal.
    BLOCKED -- a planned slice is missing its verdict, OR the slice-plan table
               is absent / unparseable; the gate stops the transition via a
               ``{"decision": "block"}`` JSON body + exit 0.
    """

    ALLOWED = "allowed"
    BLOCKED = "blocked"


class VerdictSetShape(str, Enum):
    """The shape of the signed-verdict set relative to the planned-slice set.

    COMPLETE       -- every planned slice in the ``[REF] Slice Plan`` table
                      carries a signed ``ATReviewVerdict`` record; the gate
                      allows and emits ``WorkflowPhaseCompletedDistill``.
    MISSING_ONE    -- one planned slice lacks its signed verdict; the gate
                      blocks ``DistillExitVerdictIncomplete``. Pins the
                      denominator = ``_slice_plan_slice_ids`` (MAJOR-2).
    """

    COMPLETE = "complete"
    MISSING_ONE = "missing-one"


class SlicePlanShape(str, Enum):
    """The shape of the feature-delta ``[REF] Slice Plan`` table on disk.

    PRESENT        -- a well-formed ``[REF] Slice Plan`` table with slice rows;
                      the denominator resolves.
    UNPARSEABLE    -- the feature-delta exists but carries no parseable
                      ``[REF] Slice Plan`` table; the gate blocks
                      ``SlicePlanParseUnresolved`` (fail-closed, never a
                      vacuous "zero planned slices" pass).
    """

    PRESENT = "present"
    UNPARSEABLE = "unparseable"


# Gherkin-phrase -> typed-value lookups (Mandate-12 criterion 3: no control
# flow in step bodies -- each body is a single typed lookup + composition call).

GATE_OUTCOME_BY_PHRASE: dict[str, GateOutcome] = {
    "allows the transition": GateOutcome.ALLOWED,
    "blocks the transition": GateOutcome.BLOCKED,
}

# The block event name expected per Gherkin phrase. ``allows the transition``
# carries no block event (the success terminal is asserted separately).
BLOCK_EVENT_BY_PHRASE: dict[str, str | None] = {
    "allows the transition": None,
    "an incomplete verdict set": "DistillExitVerdictIncomplete",
    "an unparseable slice plan": "SlicePlanParseUnresolved",
}
