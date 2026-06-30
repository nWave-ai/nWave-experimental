"""Domain types for the at-review-verdict-producer acceptance slice.

ADR-029 D5 / slice-07 of the atdd-pure-roadmap-free-rollout (Mandate-12
criterion 1). Every domain noun used in the Gherkin is expressed once here as a
typed enum or NewType. Step bodies and the composition service consume these
typed parameters -- no raw ``str`` where a domain enum exists.

Post-demotion: the producer writes a keyless record (no ``hmac_sha256`` field).
The signed-field enum (``SignedField``) is removed -- there is no signed-field
set post-demotion; the record's present fields are the contract.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "atdd-pure-demo").
FeatureId = NewType("FeatureId", str)

# A ``slice-NN`` slice identifier (e.g. "slice-07").
SliceId = NewType("SliceId", str)


class ReviewOutcome(str, Enum):
    """The acceptance-designer reviewer's verdict on a slice's AT set.

    APPROVED        -- the reviewer approved the AT set; the producer records an
                       ATReviewVerdict in the ledger.
    NEEDS_REVISION  -- the reviewer asked for another authoring pass; the
                       producer records NO verdict (the slice loops back).
    """

    APPROVED = "APPROVED"
    NEEDS_REVISION = "NEEDS_REVISION"


# Gherkin phrase -> ReviewOutcome (Mandate-12: parse-time coercion).
REVIEW_OUTCOME_BY_PHRASE: dict[str, ReviewOutcome] = {
    "approved the entering slice's AT set": ReviewOutcome.APPROVED,
    "asked the entering slice for revision": ReviewOutcome.NEEDS_REVISION,
}
