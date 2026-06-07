"""Domain types for slice-01 -- the `des emit-feature-end` CLI.

slice-01 of oss-feature-end-emit-cli (the R2 walking-skeleton). Every domain
noun in the slice-01 Gherkin is expressed once here as a typed enum or NewType;
step bodies and the composition service consume these typed parameters
(Mandate-12 criterion 1 -- domain types module exists with typed enums for
every domain noun used in Gherkin).

The `des emit-feature-end` command emits ONE feature-end completion-ledger
record per invocation. Two record kinds form the divergence-verification PAIR
the done-gate (`des verify-integrity`) reads as a set:

  EBatchRefactorCompleted -- the E_BATCH_REFACTOR cycle ran. Carries NO hash.
  FeatureEndReviewVerdict -- the deep review ran; binds the reviewer's signed
                             `verdict_hash` (hashed into the record_hash, so a
                             forged verdict is tamper-evident).

ANTI-THEATER INVARIANT (DDD-3): a `FeatureEndReviewVerdict` without a
`--verdict-hash` is REFUSED (non-zero exit). A hand-fabricated verdict with no
bound signed hash is theater; the CLI takes the hash from a real deep-review
signing, it does NOT mint one.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "oss-feature-end-demo").
FeatureId = NewType("FeatureId", str)

# A signed reviewer verdict hash (lowercase hex, the same HMAC the per-slice
# ATReviewVerdict carries). Bound into the FeatureEndReviewVerdict record.
VerdictHash = NewType("VerdictHash", str)


class FeatureEndRecord(str, Enum):
    """The feature-end completion-ledger record kind a single emit writes.

    BATCH_REFACTOR_COMPLETED -- the `EBatchRefactorCompleted` record; the
                                E_BATCH_REFACTOR cycle ran. No signed hash.
    DEEP_REVIEW_VERDICT      -- the `FeatureEndReviewVerdict` record; the deep
                                review ran and binds its signed verdict hash.
    """

    BATCH_REFACTOR_COMPLETED = "EBatchRefactorCompleted"
    DEEP_REVIEW_VERDICT = "FeatureEndReviewVerdict"


class EmitOutcome(str, Enum):
    """The user-observable verdict of one `des emit-feature-end` invocation.

    SUCCEEDED -- the command appended the requested record and reported success
                 (exit zero).
    REFUSED   -- the command refused the record (non-zero exit) because the
                 anti-theater invariant was violated -- a deep-review verdict
                 was requested with no bound signed hash, so no record exists.
    """

    SUCCEEDED = "succeeded"
    REFUSED = "refused"
