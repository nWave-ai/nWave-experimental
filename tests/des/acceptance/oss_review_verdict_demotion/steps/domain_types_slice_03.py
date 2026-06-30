"""Domain types for the oss-review-verdict-demotion S3 acceptance slice.

Mandate-12 criterion 1: every domain noun the S3 Gherkin names is expressed
once here as a typed enum / NewType. Step bodies and the composition service
consume these typed parameters -- no raw ``str`` where a domain enum exists.

S3 demotes the DISCUSS PO-review veto and CLOSES the unarmed-gate escape
(``subagent_stop_service.py:372``): the gate enforces record-presence with NO
signing key, an absent record ALWAYS blocks degrade-loud, and key absence
disarms nothing. The post-demotion vocabulary therefore has NO ``key-absent``
and NO ``hmac-mismatch`` reason -- those two values of the pre-demotion closed
DISCUSS reason set are RETIRED at S3 (the supersede inventory in the
feature-delta). The S3 reason vocabulary below carries only ``absent``, the
record-presence floor reason this slice pins.

S1's ``domain_types.py`` and S2's ``domain_types_slice_02.py`` own the carpaccio
gate + producer nouns; this S3-suffixed module owns the DISCUSS-gate nouns so
the three slice modules never collide on a type name (single-source per slice).
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "oss-review-verdict-demotion").
FeatureId = NewType("FeatureId", str)


class DiscussReviewVerdictState(str, Enum):
    """How the DISCUSS review verdict record is provisioned in the ledger.

    The S3 contract has three observable states -- the escape-closing absence,
    the keyless approval, and the keyless reviewer veto. Each isolates exactly
    one S3 assertion. NO state provisions a signing key; the post-demotion gate
    never resolves one.

    KEYLESS_ABSENT          -- the DISCUSS review reader is wired but the ledger
                               carries no DiscussReviewVerdict for the feature,
                               with no key provisioned anywhere. THE ESCAPE: today
                               (record None + key None) the gate returns None and
                               the handoff passes; post-demotion it ALWAYS blocks
                               INDETERMINATE (reason ``absent``). Hard contract
                               (a)/(b) -- the walking-skeleton-grade behavior change.
    KEYLESS_APPROVED_CURRENT -- a well-formed APPROVED DiscussReviewVerdict for the
                               current feature-delta, carrying NO ``hmac_sha256``
                               field, with no key provisioned. PASS leg: the gate
                               clears the handoff as "no objection found" (NOT a GO).
    KEYLESS_NEEDS_REVISION  -- a well-formed NEEDS_REVISION DiscussReviewVerdict for
                               the current feature-delta, carrying NO ``hmac_sha256``
                               field, with no key provisioned. VETO leg: the gate
                               mechanically honors the reviewer veto and blocks.
    """

    KEYLESS_ABSENT = "keyless_absent"
    KEYLESS_APPROVED_CURRENT = "keyless_approved_current"
    KEYLESS_NEEDS_REVISION = "keyless_needs_revision"


class DiscussGateDecision(str, Enum):
    """User-observable hook decision of the DISCUSS gate-OUT (allow vs block).

    Maps onto the SubagentStopService HookDecision ``action``. The DISCUSS gate
    only VETOES (asymmetric authority, §22.0): ALLOW means "no objection found",
    never an authorizing GO.
    """

    ALLOWED = "allow"
    BLOCKED = "block"


class DiscussBlockClass(str, Enum):
    """The CLASS of a DISCUSS gate block -- veto vs indeterminate (§22.7).

    The honest-verdict split: a VETO is "the reviewer said no" (a recorded
    needs-revision); an INDETERMINATE is "the verdict mechanism could not run"
    (an absent record). The two classes are DISJOINT -- a block reason carries
    its own class's token and NEVER the other's. Post-demotion the indeterminate
    class loses its keyed members (``key-absent``, ``hmac-mismatch``); the only
    indeterminate reason S3 pins is ``absent``.
    """

    REVIEWER_VETO = "reviewer_veto"
    INDETERMINATE = "indeterminate"


class DiscussRejectReason(str, Enum):
    """The DISCUSS indeterminate-block reason S3 pins (post-demotion).

    Post-demotion the closed DISCUSS reason set drops ``key-absent`` and
    ``hmac-mismatch`` (the keyed reasons -- the supersede inventory). S3 asserts
    the record-presence reason ``absent``: the no-silent-pass floor that the
    line-372 escape disarmed today (record absent + key absent -> pass blind) and
    that the demotion restores (record absent -> ALWAYS INDETERMINATE block, no
    key resolution preceding it). The SubagentStop reason string is
    ``DISCUSS_PO_REVIEW_indeterminate: absent`` -- the ``token`` is the gate-out
    sub-verdict class, the ``detail`` is this reason.
    """

    ABSENT = "absent"


# The reason-token substrings the gate's block reason carries, per class. The
# SubagentStop host renders ``DISCUSS_PO_REVIEW_{token.value}: {detail}``; the
# veto class and the indeterminate class are DISJOINT discriminants (§22.7
# honest-verdict split) -- a block reason must carry its own class's token and
# never the other class's. Post-demotion the indeterminate class loses its keyed
# members; only ``absent`` remains in S3 scope.
VETO_REASON_TOKENS: tuple[str, ...] = ("vetoed", "needs-revision", "not-approved")
INDETERMINATE_REASON_TOKENS: tuple[str, ...] = ("indeterminate", "absent")


# Gherkin-phrase -> typed-value lookups. Module-level dicts keep each step body
# a single typed lookup + a single composition call (Mandate-12 criterion 3:
# no control flow in step bodies).

RECORD_STATE_BY_PHRASE: dict[str, DiscussReviewVerdictState] = {
    (
        "an approved product-owner review verdict recorded with no signature "
        "for the current artefact"
    ): DiscussReviewVerdictState.KEYLESS_APPROVED_CURRENT,
    (
        "a needs-revision product-owner review verdict recorded with no signature "
        "for the current artefact"
    ): DiscussReviewVerdictState.KEYLESS_NEEDS_REVISION,
}

DECISION_BY_PHRASE: dict[str, DiscussGateDecision] = {
    "allowed as no objection found from the review": DiscussGateDecision.ALLOWED,
    "blocked degrade-loud as indeterminate": DiscussGateDecision.BLOCKED,
    "blocked by the reviewer veto": DiscussGateDecision.BLOCKED,
}

REJECT_REASON_BY_PHRASE: dict[str, DiscussRejectReason] = {
    "absent": DiscussRejectReason.ABSENT,
}
