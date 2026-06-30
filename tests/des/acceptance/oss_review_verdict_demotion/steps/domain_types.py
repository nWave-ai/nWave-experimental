"""Domain types for the oss-review-verdict-demotion S1 acceptance slice.

Mandate-12 criterion 1: every domain noun used in the Gherkin is expressed once
here as a typed enum / NewType. Step bodies and the composition service consume
these typed parameters -- no raw ``str`` where a domain enum exists.

S1 demotes the AT-review slice gate from "HMAC-signed verdict" to
"record present and well-formed". The post-demotion vocabulary therefore has
NO ``key-absent`` and NO ``hmac-mismatch`` reason -- those two values of the
pre-demotion closed set are RETIRED at S1 (the supersede inventory in the
feature-delta). The S1 reason vocabulary below carries only ``absent``, the
record-presence veto reason this slice pins.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "oss-review-verdict-demotion").
FeatureId = NewType("FeatureId", str)

# A ``slice-NN`` slice identifier (e.g. "slice-01").
SliceId = NewType("SliceId", str)


class GateVerdict(str, Enum):
    """User-observable verdict of one carpaccio-slice-gate invocation.

    Maps onto the gate CLI exit-code contract (ADR-028 D2-bis + ADR-029 D5).
    Only the two outcomes S1 asserts are modelled: a cleared slice (exit 0)
    and an AT-review rejection (exit 45). The other exit codes (1, 2, 44) are
    out of S1 scope -- the carpaccio decomposition legs are untouched by the
    signing demotion (feature-delta DISCUSS [REF] Out-of-Scope).
    """

    CLEARED = "cleared"  # exit 0
    AT_REVIEW_REJECTED = "at_review_rejected"  # exit 45


class ReviewVerdictRecordState(str, Enum):
    """How the review verdict record is provisioned in the AT-completion ledger.

    The S1 contract has three observable states -- the keyless happy path, the
    record-absence block, and the legacy-record tolerance. Each isolates exactly
    one S1 assertion. NO state provisions a signing key; the post-demotion gate
    never resolves one.

    KEYLESS_APPROVED   -- a well-formed APPROVED record matching the slice's AT
                          set by id and content hash, carrying NO ``hmac_sha256``
                          field and with no key provisioned anywhere. Hard
                          contract (b)/(d) PASS path; the walking skeleton.
    ABSENT             -- the ledger exists but carries no review verdict for the
                          entering slice. Hard contract (b): record-absence
                          ALWAYS blocks (reason ``absent``), no-silent-pass spine.
    LEGACY_WITH_HMAC   -- a well-formed APPROVED record that ALSO still carries a
                          stray ``hmac_sha256`` field (a pre-demotion operational
                          record), with no key provisioned. Hard contract (c):
                          tolerated-and-ignored, no verify attempt, no parse error.
    """

    KEYLESS_APPROVED = "keyless_approved"
    ABSENT = "absent"
    LEGACY_WITH_HMAC = "legacy_with_hmac"


class ATReviewRejectReason(str, Enum):
    """The AT-review rejection reason S1 pins (post-demotion).

    Post-demotion the closed reason set drops ``key-absent`` and
    ``hmac-mismatch`` (the keyed reasons -- the supersede inventory). S1 asserts
    the record-presence reason ``absent``: the no-silent-pass spine that holds
    before the demotion (record absent -> block) AND after (still blocks, now
    with no key resolution preceding it).
    """

    ABSENT = "absent"


# Gherkin-phrase -> typed-value lookups. Module-level dicts keep each step body
# a single typed lookup + a single composition call (Mandate-12 criterion 3:
# no control flow in step bodies).

RECORD_STATE_BY_PHRASE: dict[str, ReviewVerdictRecordState] = {
    "an approved review verdict recorded with no signature": (
        ReviewVerdictRecordState.KEYLESS_APPROVED
    ),
    "an approved review verdict recorded carrying a legacy signature field": (
        ReviewVerdictRecordState.LEGACY_WITH_HMAC
    ),
}

VERDICT_BY_PHRASE: dict[str, GateVerdict] = {
    "cleared to enter implementation": GateVerdict.CLEARED,
    "blocked with an AT-review rejection": GateVerdict.AT_REVIEW_REJECTED,
}

REJECT_REASON_BY_PHRASE: dict[str, ATReviewRejectReason] = {
    "absent": ATReviewRejectReason.ABSENT,
}
