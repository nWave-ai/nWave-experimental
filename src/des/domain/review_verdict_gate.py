"""Wave-parametric review-verdict veto-gate pure core (f-design-devops-review-gate).

The generic core extracted from ``discuss_review_gate.DiscussReviewGate`` (DDD-1,
Mandate-12 SSOT): the PASS / VETOED / INDETERMINATE decision + no-silent-pass +
stale-artefact path are wave-agnostic in substance -- only the token-class names
were DISCUSS-spelled. This module holds the ONE verdict home so a second wave
(DESIGN / DEVOPS) reuses the verdict logic with zero copy.

Pure verification over an already-read review-verdict ledger record; NO I/O, NO
key. The ledger READ and the feature-delta hash computation live in the thin
consumer CLI + the driven reader port -- never here.

Asymmetric authority (§22.0 / §21.1.3): a NEEDS_REVISION is a mechanically-
honored VETO; an artefact-current APPROVED is "no objection found", NEVER an
authorizing GO (the GO stays human). Absent verdicts are INDETERMINATE
(degrade-LOUD, §17): NEVER coerced to PASS (no-silent-pass) and NEVER coerced
to VETOED ("the verdict mechanism could not run" must never masquerade as "the
reviewer said no" -- §22.7 honest-verdict split).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# The reviewer-outcome literals a wave reviewer records (O-4 both-outcomes,
# DDD-6). Wave-agnostic: the producer CLI writes BOTH so a veto is mechanically
# readable; an un-written NEEDS_REVISION would collapse into INDETERMINATE
# alongside "no review yet", defeating the veto.
REVIEW_APPROVED = "approved"
REVIEW_NEEDS_REVISION = "needs-revision"

# The record schema versions this verifier knows how to read (§21.2.3: an
# unknown schema is never confidently mis-parsed -- it degrades LOUD).
_KNOWN_SCHEMA_VERSIONS: tuple[str, ...] = ("1.0.0",)


class ReviewGateToken(str, Enum):
    """Closed set -- the gate-OUT sub-verdict the consumer reads.

    The §17 GateVerdict projection the wave gate-out emits (DDD-7, ADR-GV-001 --
    no sixth verdict).
    """

    PASS = "pass"  # APPROVED, artefact-current -> no objection found
    VETOED = "vetoed"  # NEEDS_REVISION -> mechanically honored veto
    INDETERMINATE = "indeterminate"  # absent / stale / schema-unknown -> degrade-LOUD


@dataclass(frozen=True)
class ReviewGateResult:
    """The review-verdict gate decision VO.

    INVARIANT: ``token`` is the ONLY authority the gate-OUT host reads;
    ``detail`` is one of the closed rejection reasons (``absent`` |
    ``not-approved`` (-> VETOED) | ``stale-artefact`` | ``schema-unknown``).
    INVARIANT: a NEEDS_REVISION -> VETOED (a control veto, §22.0);
    APPROVED + artefact-current -> PASS ("no objection found", NOT authorization).
    INVARIANT: absent/stale/schema-unknown -> INDETERMINATE (degrade-LOUD, §17
    N=0), NEVER coerced to PASS and NEVER coerced to VETOED.
    """

    token: ReviewGateToken
    detail: str


def _indeterminate(detail: str) -> ReviewGateResult:
    return ReviewGateResult(token=ReviewGateToken.INDETERMINATE, detail=detail)


class ReviewVerdictGate:
    """Wave-parametric pure-CORE verification of a review-verdict record.

    Keyless record-presence veto: no signing key, no HMAC. Pre-existing
    ``hmac_sha256`` fields on legacy records are tolerated-and-ignored
    (D-tolerate-old, upgrade-compat). The same evaluation serves DISCUSS,
    DESIGN, and DEVOPS -- the wave is carried by the event-name the reader
    selects on, not by the verdict logic.
    """

    @staticmethod
    def evaluate(
        record: dict[str, object] | None,
        expected_feature_delta_hash: str,
    ) -> ReviewGateResult:
        """Verify the latest review-verdict record, fail-closed.

        ORDER (fail-closed, no key resolution):
          record is None           -> INDETERMINATE("absent")        [no verdict recorded]
          schema_version unknown   -> INDETERMINATE("schema-unknown")
          feature_delta_hash drift -> INDETERMINATE("stale-artefact")
          verdict NEEDS_REVISION   -> VETOED("not-approved")         [reviewer veto]
          verdict APPROVED         -> PASS                           [no objection, NOT GO]

        Legacy ``hmac_sha256`` fields on old records are silently ignored
        (tolerate-and-ignore, D-tolerate-old). Key absence is a non-event.
        """
        if record is None:
            return _indeterminate("absent")
        if record.get("schema_version") not in _KNOWN_SCHEMA_VERSIONS:
            return _indeterminate("schema-unknown")
        if record.get("feature_delta_hash") != expected_feature_delta_hash:
            return _indeterminate("stale-artefact")
        verdict = record.get("verdict")
        if verdict == REVIEW_NEEDS_REVISION:
            return ReviewGateResult(token=ReviewGateToken.VETOED, detail="not-approved")
        if verdict == REVIEW_APPROVED:
            return ReviewGateResult(
                token=ReviewGateToken.PASS,
                detail="no objection found from the review",
            )
        # A record whose verdict literal is outside the closed reviewer-outcome
        # set is not a reviewer decision the gate can read -- degrade LOUD,
        # never coerce to PASS or VETOED (§22.7).
        return _indeterminate("schema-unknown")
