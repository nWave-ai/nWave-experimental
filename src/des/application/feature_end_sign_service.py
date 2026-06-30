"""Platform-agnostic deep-review signing use-case (DDD-7, slice-02).

slice-02 of oss-feature-end-emit-cli. This is the PRODUCER half of the
feature-end deep-review leg: it turns a REAL reviewer deep-review verdict
(agent + APPROVED/REJECTED + findings) into a deterministic content hash
(``verdict_hash``) via the ``des.domain.at_review_signing`` SSOT. The produced
hex is the input slice-01's ``des emit-feature-end --record FeatureEndReviewVerdict
--verdict-hash`` consumes.

ANTI-THEATER INVARIANT (DDD-5, load-bearing, per ``feedback_earned_trust_
mechanical_evidence_not_llm_verdict``): the signer NEVER MINTS. It requires the
reviewer's real verdict record and content-hashes it via
``sha256(canonical_signed_json(signed_region, SIGNED_FIELDS))``. A sign request
with no real verdict / a malformed-or-empty verdict is REFUSED -- no hash is
produced. Key absence is a non-event (OSS demotion, oss-review-verdict-demotion
S4): the signed region is hashed deterministically without a key.

DDD-7 separation: this is the platform-agnostic DECISION logic. The
``des feature-end sign`` CLI shim (and the eventual SubagentStop hook shim)
carry NO decision logic -- they marshal I/O and invoke this use-case. The signed
region reuses the seven ``at_review_signing.SIGNED_FIELDS``: a deep-review
verdict maps onto them as ``slice_id="feature-end"``, ``timestamp=
"feature-end-review"``, ``at_ids=[]``, ``at_content_hash=<feature_id>``.

Stdlib-only at this layer (hashlib + canonical JSON), so the use-case is
bundle-safe and host-agnostic.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.domain.at_review_signing import (
    SIGNED_FIELDS,
    canonical_at_review_json,
    canonical_signed_json,
)


if TYPE_CHECKING:
    from pathlib import Path


# The signed-region constants binding a deep-review verdict onto the seven
# at_review_signing SIGNED_FIELDS. These are the mapping the independent recompute
# (the AT's genuineness oracle) reproduces byte-for-byte; a divergence here breaks
# the equality check, which is the anti-theater guard working.
_SCHEMA_VERSION = "1.0.0"
_SLICE_ID = "feature-end"
_TIMESTAMP = "feature-end-review"

# The verdict values a REAL deep-review carries. Anything else is a non-real
# verdict the anti-theater invariant refuses (the C6 refusal matrix).
_KNOWN_VERDICTS = ("APPROVED", "REJECTED")


@dataclass(frozen=True)
class SignSuccess:
    """A deterministic content hash was produced over the real deep-review verdict."""

    verdict_hash: str


@dataclass(frozen=True)
class SignRefusal:
    """The signer refused: the anti-theater invariant was violated, no hash."""

    error: str


def sign_feature_end_review(
    *,
    feature_id: str | None,
    reviewer_agent_id: str | None,
    verdict: str | None,
    repo_root: Path,
) -> SignSuccess | SignRefusal:
    """Produce a deterministic content ``verdict_hash`` over a real deep-review verdict.

    Returns :class:`SignSuccess` carrying the content hash when the verdict is
    real, otherwise :class:`SignRefusal` naming the violated anti-theater
    precondition -- never a minted hash.

    A real deep-review verdict has a non-empty ``feature_id``, a non-empty
    ``reviewer_agent_id``, and a ``verdict`` the signer recognizes
    (APPROVED/REJECTED). Key absence is a non-event: the hash is computed
    deterministically from the signed region alone (OSS demotion S4).

    ``repo_root`` is accepted for API-stability (callers already supply it) but
    is not read: no key is resolved post-demotion.
    """
    if not feature_id or not feature_id.strip():
        return SignRefusal("no feature id supplied; cannot sign a verdict")
    if not reviewer_agent_id or not reviewer_agent_id.strip():
        return SignRefusal(
            "no reviewer agent supplied; a real deep-review verdict names its "
            "reviewer (anti-theater)"
        )
    if verdict is None:
        return SignRefusal(
            "no deep-review verdict supplied; the decision was never made "
            "(anti-theater)"
        )
    if verdict not in _KNOWN_VERDICTS:
        return SignRefusal(
            f"unknown deep-review verdict {verdict!r}; a real verdict is one of "
            f"{', '.join(_KNOWN_VERDICTS)} (anti-theater)"
        )

    signed_region = _signed_region(
        feature_id=feature_id,
        reviewer_agent_id=reviewer_agent_id,
        verdict=verdict,
    )
    verdict_hash = hashlib.sha256(
        canonical_signed_json(signed_region, SIGNED_FIELDS)
    ).hexdigest()
    return SignSuccess(verdict_hash)


def _signed_region(
    *, feature_id: str, reviewer_agent_id: str, verdict: str
) -> dict[str, object]:
    """The seven-SIGNED_FIELDS record content-hashed for a deep-review verdict.

    Reuses the ``at_review_signing`` SSOT field names. The mapping is the
    content-hash contract the independent recompute reproduces; the canonical
    serializer (``canonical_signed_json``) sorts keys, so the order here is
    irrelevant to the hashed bytes -- only the field set + values matter.
    """
    record: dict[str, object] = {
        "schema_version": _SCHEMA_VERSION,
        "slice_id": _SLICE_ID,
        "verdict": verdict,
        "reviewer_agent_id": reviewer_agent_id,
        "at_ids": [],
        "at_content_hash": feature_id,
        "timestamp": _TIMESTAMP,
    }
    # Touch the canonical serializer here so a future field-set drift fails this
    # module's own bundle-safe invariant rather than silently producing a hash
    # over the wrong bytes.
    canonical_at_review_json(record)
    return record
