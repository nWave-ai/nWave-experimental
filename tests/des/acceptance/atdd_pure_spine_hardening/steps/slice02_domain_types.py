"""Domain types for slice-02 -- the U2 G_COMMIT SubagentStop exit-gate intercept.

slice-02 of F-DES-ATDD-PURE-HOOK-GATES (U2 / Mikado T-G). Every domain noun in
the slice-02 Gherkin is expressed once here as a typed enum or NewType; step
bodies and the composition service consume these typed parameters
(Mandate-12 criterion 1).

U2 intercepts an atdd_pure crafter returning from the `G_COMMIT` phase: it runs
the slice-commit completeness exit gate (E1) and the contract gate (E2) against
a pinned commit SHA, and blocks the orchestrator via `{decision: block}` +
exit 0 when either gate fails. A handler exception is itself an
`AtddPureHookInternalError` block (exit 0), never a bare exit 1.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "atdd-pure-demo").
FeatureId = NewType("FeatureId", str)

# A carpaccio slice identifier (e.g. "slice-02").
SliceId = NewType("SliceId", str)


class GateOutcome(str, Enum):
    """The user-observable verdict of the U2 G_COMMIT SubagentStop intercept.

    ALLOWED -- both exit gates passed; the orchestrator proceeds.
    BLOCKED -- a gate failed (or the handler raised); the orchestrator is
               stopped via a `{"decision": "block"}` JSON body + exit 0.
    """

    ALLOWED = "allowed"
    BLOCKED = "blocked"


class CommitShape(str, Enum):
    """The shape of the HEAD commit the returning crafter produced.

    COMPLETE       -- a single-slice commit whose `.feature` AT files are all
                      present; E1 passes.
    BATCHED        -- a multi-`Slice-Id` batched commit; E1 verifies the whole
                      listed slice set (F-07 -- the batched commit is accepted,
                      not rejected).
    INCOMPLETE     -- a commit missing the slice's `.feature` AT files; E1 fails.
    NO_SLICE_ID    -- a commit carrying no `Slice-Id:`/`Step-Id:` trailer at
                      all; the slice is not closeable.
    """

    COMPLETE = "complete"
    BATCHED = "batched"
    INCOMPLETE = "incomplete"
    NO_SLICE_ID = "no-slice-id"


class HandlerFault(str, Enum):
    """Whether a fault is injected inside the U2 atdd_pure branch.

    NONE     -- the branch runs normally.
    RAISES   -- the branch body raises an exception; M1 requires the handler to
                emit an `AtddPureHookInternalError` block + exit 0, never the
                generic bare-exit-1 path.
    """

    NONE = "none"
    RAISES = "raises"


# Gherkin-phrase -> typed-value lookups (Mandate-12 criterion 3: no control
# flow in step bodies -- each body is a single typed lookup + composition call).

COMMIT_SHAPE_BY_PHRASE: dict[str, CommitShape] = {
    "a complete slice commit": CommitShape.COMPLETE,
    "a multi-slice batched commit": CommitShape.BATCHED,
    "an incomplete slice commit": CommitShape.INCOMPLETE,
    "a commit with no slice trailer": CommitShape.NO_SLICE_ID,
}

GATE_OUTCOME_BY_PHRASE: dict[str, GateOutcome] = {
    "is allowed": GateOutcome.ALLOWED,
    "is blocked": GateOutcome.BLOCKED,
}
