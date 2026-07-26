"""DISCUSS PO-review veto-gate (slice-07b, nwave-flow-v2-enforcement).

SHAPE per DESIGN feature-delta § "Wave: DESIGN / [REF] slice-07b code-design
(DISCUSS PO-review MECHANICAL veto-gate -- O-3 resolution)". The DISCUSS-spelled
binding over the wave-parametric ``ReviewVerdictGate`` pure core
(f-design-devops-review-gate, DDD-1): the verdict logic lives ONCE in
``review_verdict_gate``; this module is the DISCUSS-named facade that preserves
the existing public surface (``DiscussReviewToken`` / ``DiscussReviewGateToken``
/ ``DiscussReviewGateResult`` / ``DiscussReviewGate.evaluate`` /
``DISCUSS_REVIEW_EVENT``) the consumers import.

Asymmetric authority (§22.0 / §21.1.3): a NEEDS_REVISION is a mechanically-
honored VETO; an artefact-current APPROVED is "no objection found", NEVER an
authorizing GO. Absent verdicts are INDETERMINATE (degrade-LOUD, §17): NEVER
coerced to PASS (no-silent-pass) and NEVER coerced to VETOED (§22.7 honest-
verdict split).

Post-demotion (oss-review-verdict-demotion S3): the keyed HMAC is removed. The
record-presence check is the control; key absence disarms nothing. Pre-existing
``hmac_sha256`` fields on old records are tolerated-and-ignored (D-tolerate-old).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from des.domain.review_verdict_gate import ReviewGateToken, ReviewVerdictGate
from des.domain.wave_review_spec import DISCUSS_REVIEW_SPEC


# The DISCUSS-scoped verdict event name -- the record-family discriminant the
# reader selects on (analogous to ``ATReviewVerdict``, keyed by feature).
# Sourced from the wave spec so the three wave event names have ONE origin.
DISCUSS_REVIEW_EVENT = DISCUSS_REVIEW_SPEC.event


class DiscussReviewToken(str, Enum):
    """Closed set -- what the gate reads from the signed record."""

    APPROVED = "approved"  # reviewer found no blocking objection (NOT a GO -- §22.0)
    NEEDS_REVISION = "needs-revision"  # reviewer VETO -> block handoff to DESIGN


class DiscussReviewGateToken(str, Enum):
    """Closed set -- the gate-OUT sub-verdict the SubagentStop host reads."""

    PASS = "pass"  # APPROVED, artefact-current -> no objection found
    VETOED = "vetoed"  # NEEDS_REVISION -> mechanically honored veto
    INDETERMINATE = "indeterminate"  # absent -> degrade-LOUD block


@dataclass(frozen=True)
class DiscussReviewGateResult:
    """The PO-review gate decision VO.

    INVARIANT: ``token`` is the ONLY authority the gate-OUT host reads;
    ``detail`` is one of the closed rejection reasons (``absent`` |
    ``not-approved`` (-> VETOED) | ``stale-artefact`` | ``schema-unknown``).
    INVARIANT: a NEEDS_REVISION -> VETOED (a control veto, §22.0);
    APPROVED + artefact-current -> PASS ("no objection found", NOT authorization).
    INVARIANT: absent/stale/schema-unknown ->
    INDETERMINATE (degrade-LOUD, §17 N=0), NEVER coerced to PASS and NEVER
    coerced to VETOED.
    """

    token: DiscussReviewGateToken
    detail: str


# The generic-core token -> the DISCUSS-spelled gate token. The two enums carry
# the identical closed value set ("pass"/"vetoed"/"indeterminate"); the map keeps
# the DISCUSS public surface stable while the decision lives in the generic core.
_TOKEN_FROM_GENERIC: dict[ReviewGateToken, DiscussReviewGateToken] = {
    ReviewGateToken.PASS: DiscussReviewGateToken.PASS,
    ReviewGateToken.VETOED: DiscussReviewGateToken.VETOED,
    ReviewGateToken.INDETERMINATE: DiscussReviewGateToken.INDETERMINATE,
}


class DiscussReviewGate:
    """DISCUSS-named facade over the wave-parametric ``ReviewVerdictGate`` core.

    Post-demotion (oss-review-verdict-demotion S3): keyless record-presence
    veto. No signing key, no HMAC. Pre-existing ``hmac_sha256`` fields on
    legacy records are tolerated-and-ignored (D-tolerate-old, upgrade-compat).
    """

    @staticmethod
    def evaluate(
        record: dict[str, object] | None,
        expected_feature_delta_hash: str,
    ) -> DiscussReviewGateResult:
        """Verify the latest ``DiscussReviewVerdict`` record, fail-closed.

        Delegates the verdict logic to the generic ``ReviewVerdictGate.evaluate``
        core (behaviour-preserving) and re-spells the result onto the DISCUSS
        gate token the consumers read. The decision ORDER (absent ->
        schema-unknown -> stale-artefact -> NEEDS_REVISION -> APPROVED) and every
        detail string are the core's, unchanged.
        """
        result = ReviewVerdictGate.evaluate(record, expected_feature_delta_hash)
        return DiscussReviewGateResult(
            token=_TOKEN_FROM_GENERIC[result.token], detail=result.detail
        )
