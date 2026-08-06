"""Domain types for the des-verify-integrity mode-aware acceptance slice.

ADR-028 D4.2 / slice-02 of the ATDD-pure rollout (Mandate-12
criterion 1). Every domain noun used in the Gherkin is expressed once here as
a typed enum or NewType. Step bodies and the composition service consume these
typed parameters -- no raw `str` where a domain enum exists.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


class WorkflowMode(str, Enum):
    """The project workflow mode resolved from .nwave/config.yaml:workflow.mode.

    ATDD_PURE -- the only supported delivery spine.
    UNSET     -- no explicit key; it resolves to ATDD_PURE.
    """

    ATDD_PURE = "atdd_pure"
    UNSET = "unset"


class LedgerState(str, Enum):
    """Presence/shape of the AT-completion ledger for an atdd_pure feature.

    PRESENT_ALL_SHIPPED -- ledger exists and every slice-plan row is `shipped`.
    ABSENT              -- no AT-completion ledger file. Under atdd_pure this is
                           a verification FAILURE with a structured diagnostic
                           (exit 1), never a crash (ADR-028 D3).
    """

    PRESENT_ALL_SHIPPED = "present_all_shipped"
    ABSENT = "absent"


class IntegrityVerdict(str, Enum):
    """The user-observable verdict of one des-verify-integrity invocation.

    Maps onto the CLI exit-code contract.
    """

    VERIFIED = "verified"  # exit 0
    VIOLATION = "violation"  # exit 1
    USAGE_ERROR = "usage_error"  # exit 2


# Gherkin-phrase -> typed-value lookups. Keeping these as module-level dicts
# lets each step body stay a single typed lookup + a single composition call
# (Mandate-12 criterion 3: no control flow in step bodies).

VERDICT_BY_PHRASE: dict[str, IntegrityVerdict] = {
    "the feature verified": IntegrityVerdict.VERIFIED,
    "an integrity violation": IntegrityVerdict.VIOLATION,
}


# A kebab-case feature identifier (e.g. "atdd-pure-demo").
FeatureId = NewType("FeatureId", str)
