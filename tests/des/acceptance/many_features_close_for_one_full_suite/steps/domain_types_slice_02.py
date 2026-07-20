"""Typed-parameter vocabulary for slice-02 (batch-eligibility precheck)
Gherkin steps -- mirrors `domain_types_slice_01.py`'s typed-dispatch pattern
(Mandate-12 criterion 2: never a raw string dispatch in a step body).

D-5 (Locked Decisions): "every batch member's Slice-Plan slices are
SliceCommitVerified, its deep-review is APPROVED, and its critical charters
are EXAMINE-PASSed at run start." `EligibilityFailureMode` is the closed set
of the 3 ineligibility signals a Gherkin `Given` selects between; every
per-mode table below is the single dispatch surface `composition_slice_02.py`
consumes -- never a raw string branch in a step body.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class EligibilityFailureMode(Enum):
    """The 3 D-5 ineligibility signals (Given-clause phrase = enum value)."""

    UNDELIVERED_SLICE = "whose Slice-Plan slice was never delivered"
    NON_APPROVED_VERDICT = "declaring a non-approved deep-review verdict"
    FAILED_CHARTER = "whose critical charter failed EXAMINE"


FAILURE_MODE_BY_TEXT: dict[str, EligibilityFailureMode] = {
    mode.value: mode for mode in EligibilityFailureMode
}

INELIGIBLE_ID_BY_MODE: dict[EligibilityFailureMode, str] = {
    EligibilityFailureMode.UNDELIVERED_SLICE: "feature-not-delivered",
    EligibilityFailureMode.NON_APPROVED_VERDICT: "feature-not-approved",
    EligibilityFailureMode.FAILED_CHARTER: "feature-charter-failed",
}

#: The `EligibilityBatchFixture` method name that seeds EXACTLY the ONE
#: ineligibility signal this mode names (every other D-5 axis stays clean).
SEED_METHOD_BY_MODE: dict[EligibilityFailureMode, str] = {
    EligibilityFailureMode.UNDELIVERED_SLICE: "seed_truncated_feature",
    EligibilityFailureMode.NON_APPROVED_VERDICT: "seed_feature_with_rejected_verdict",
    EligibilityFailureMode.FAILED_CHARTER: "seed_feature_with_failed_charter",
}

#: The manifest verdict written for the INELIGIBLE member -- REJECTED only
#: for the verdict-axis mode; every other mode's member carries a genuinely
#: APPROVED verdict so its OWN ineligibility signal is the sole variable.
INELIGIBLE_VERDICT_BY_MODE: dict[EligibilityFailureMode, str] = {
    EligibilityFailureMode.UNDELIVERED_SLICE: "APPROVED",
    EligibilityFailureMode.NON_APPROVED_VERDICT: "REJECTED",
    EligibilityFailureMode.FAILED_CHARTER: "APPROVED",
}

#: Substrings the batch-level refusal's `error` text must contain, naming
#: WHICH check failed (GDP-3).
CHECK_SUBSTRINGS_BY_MODE: dict[EligibilityFailureMode, tuple[str, ...]] = {
    EligibilityFailureMode.UNDELIVERED_SLICE: (
        "SliceCommitVerified",
        "undelivered",
        "slice-02",
    ),
    EligibilityFailureMode.NON_APPROVED_VERDICT: ("deep-review", "verdict", "APPROVED"),
    EligibilityFailureMode.FAILED_CHARTER: ("EXAMINE", "charter"),
}


@dataclass(frozen=True)
class MixedBatchSeed:
    """The observable seeding outcome a negative `Given` step exposes to the
    `When`/`Then` steps via `state_02` -- port-exposed values only
    (Mandate 8 Universe): a manifest path plus the pre-declared ineligible
    feature id and check-name substrings the `Then` oracle checks against."""

    manifest_path: Path
    ineligible_feature_id: str
    check_substrings: tuple[str, ...]


__all__ = [
    "CHECK_SUBSTRINGS_BY_MODE",
    "FAILURE_MODE_BY_TEXT",
    "INELIGIBLE_ID_BY_MODE",
    "INELIGIBLE_VERDICT_BY_MODE",
    "SEED_METHOD_BY_MODE",
    "EligibilityFailureMode",
    "MixedBatchSeed",
]
