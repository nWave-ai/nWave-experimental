"""Domain types for the oss-review-verdict-demotion S6 acceptance slice.

Mandate-12 criterion 1: every domain noun used in the Gherkin is expressed once
here as a typed enum / NewType. Step bodies and the composition service consume
these typed parameters -- no raw ``str`` where a domain enum exists.

S6 consolidates the demotion's CLI surface: the trailer-derivation CLI is
HARD-DELETED and the commit-trailer verifier is REPURPOSED to a ledger-record
audit window over the carpaccio gate's verdict logic. The vocabulary below is
the repurposed-verifier's observable surface (an audit verdict + the gate's own
closed rejection-reason set) plus the deletion-safety surface (the absent
derivation command).
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "oss-review-verdict-demotion").
FeatureId = NewType("FeatureId", str)

# A ``slice-NN`` slice identifier (e.g. "slice-01").
SliceId = NewType("SliceId", str)


class AuditVerdict(str, Enum):
    """User-observable verdict of one verify-commit-trailers audit invocation.

    The repurposed verifier audits a commit's review record and reaches the
    SAME verdict the carpaccio slice gate reaches -- or, when the commit
    carries no ``Slice-Id:`` trailer, the honest nothing-to-audit
    INDETERMINATE (A-absent-trailer, architect-final 2026-06-11): never a
    silent exit-0, never a BLOCK (non-slice commits are legitimate).
    """

    PRESENT_AND_APPROVED = "present_and_approved"  # exit 0
    REFUSED = "refused"  # the gate's rejection surfaced
    NOTHING_TO_AUDIT = "nothing_to_audit"  # exit 7 INDETERMINATE


# A-absent-trailer (architect-final 2026-06-11): the nothing-to-audit
# INDETERMINATE reuses the verifier's ALREADY-EXISTING exit-7 cannot-evaluate
# channel (zero new exit code); the stderr reason distinguishes it from the
# git-absent INDETERMINATE.
NOTHING_TO_AUDIT_EXIT = 7
NOTHING_TO_AUDIT_REASON = "no Slice-Id trailer"


class ReviewRecordState(str, Enum):
    """How the audited commit's review verdict record is provisioned.

    The S6 contract has two ledger states plus the deletion-safety surface.
    NO state provisions a signing key; the repurposed verifier never resolves
    one (it reads the record's present fields, exactly as the gate does).

    APPROVED_NO_SIGNATURE -- a well-formed APPROVED record matching the slice's
                             AT set by id and content hash, carrying NO
                             ``hmac_sha256`` field. The audit-clears path; the
                             walking skeleton.
    NOT_APPROVED          -- a recorded review whose verdict is not APPROVED
                             (e.g. NEEDS_REVISION). The no-drift spine: the
                             carpaccio gate refuses with reason ``not-approved``
                             and the audit window MUST refuse with the same
                             reason.
    """

    APPROVED_NO_SIGNATURE = "approved_no_signature"
    NOT_APPROVED = "not_approved"


class GateRejectReason(str, Enum):
    """The closed AT-review rejection-reason set the carpaccio gate emits.

    This is the gate's OWN closed vocabulary (carpaccio_format._at_review_rejection):
    ``absent`` / ``not-approved`` / ``stale-at-set`` / ``stale-at-content`` /
    ``no-scenarios-for-slice``. The repurposed verifier is an audit window over
    the gate's verdict logic, so it surfaces a refusal with the SAME reason the
    gate would -- never a reason of its own. S6 pins the ``not-approved`` leg as
    the no-drift witness; the post-demotion keyed reasons (``key-absent`` /
    ``hmac-mismatch``) are absent from the set (retired at S1).
    """

    NOT_APPROVED = "not-approved"


class DerivationCommandState(str, Enum):
    """Whether the reviewer-trailer derivation command exists.

    S6 HARD-DELETES ``scripts/cli/derive_review_trailer.py``. The deletion-safety
    surface has exactly one observable post-demotion state: ABSENT.
    """

    ABSENT = "absent"


# Gherkin-phrase -> typed-value lookups. Module-level dicts keep each step body
# a single typed lookup + a single composition call (Mandate-12 criterion 3:
# no control flow in step bodies).

RECORD_STATE_BY_PHRASE: dict[str, ReviewRecordState] = {
    "an approved review verdict recorded with no signature": (
        ReviewRecordState.APPROVED_NO_SIGNATURE
    ),
    "a review verdict recorded that was not approved": ReviewRecordState.NOT_APPROVED,
}

GATE_REASON_BY_PHRASE: dict[str, GateRejectReason] = {
    "not-approved": GateRejectReason.NOT_APPROVED,
}
