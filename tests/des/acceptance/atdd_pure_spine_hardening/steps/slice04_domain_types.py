"""Domain types for slice-04 -- the U4 feature-end intercept + D6 skew contract.

slice-04 of F-DES-ATDD-PURE-HOOK-GATES (U4 + D6 / Mikado T-H). Every domain
noun in the slice-04 Gherkin is expressed once here as a typed enum or NewType;
step bodies and the composition service consume these typed parameters
(Mandate-12 criterion 1).

U4 intercepts an atdd_pure feature-end review agent returning from the
`F_FINAL_REVIEW` phase: when every planned slice is shipped (derived from the
U3 ledger under the M7 fail-closed read contract) it runs the feature-end
integrity gate. A corrupt ledger blocks with `LedgerIntegrityViolation`; a
handler exception is an `AtddPureHookInternalError` block (exit 0).

D6 stamps `nwave_hook_version` and classifies skew into three M13 cases.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "atdd-pure-demo").
FeatureId = NewType("FeatureId", str)


class FeatureEndOutcome(str, Enum):
    """The user-observable verdict of the U4 feature-end SubagentStop intercept.

    ALLOWED -- every planned slice is shipped and the integrity gate passed;
               the feature is closeable.
    BLOCKED -- the ledger is unusable, or the handler raised; the orchestrator
               is stopped via a `{"decision": "block"}` JSON body + exit 0.
    """

    ALLOWED = "allowed"
    BLOCKED = "blocked"


class LedgerShape(str, Enum):
    """The shape of the AT-completion ledger the feature-end intercept reads.

    ALL_VERIFIED   -- every planned slice carries a terminal
                      `SliceCommitVerified` record; the integrity gate runs.
    CORRUPT        -- the ledger is present but fails the M7 integrity contract
                      (a hand-edited record breaks the `record_hash`); U4
                      blocks with `LedgerIntegrityViolation`, NEVER degrading
                      to the markdown fallback.
    FAULT_INJECTED -- a fault is injected inside the U4 atdd_pure branch; M1
                      requires an `AtddPureHookInternalError` block + exit 0.
    """

    ALL_VERIFIED = "all-verified"
    CORRUPT = "corrupt"
    FAULT_INJECTED = "fault-injected"


# Gherkin-phrase -> typed-value lookups (Mandate-12 criterion 3: no control
# flow in step bodies -- each body is a single typed lookup + composition call).

LEDGER_SHAPE_BY_PHRASE: dict[str, LedgerShape] = {
    "corrupt": LedgerShape.CORRUPT,
    "fault-injected": LedgerShape.FAULT_INJECTED,
}

FEATURE_END_OUTCOME_BY_PHRASE: dict[str, FeatureEndOutcome] = {
    "is allowed": FeatureEndOutcome.ALLOWED,
    "is blocked": FeatureEndOutcome.BLOCKED,
}
