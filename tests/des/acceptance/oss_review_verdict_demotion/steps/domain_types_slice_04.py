"""Domain types for the oss-review-verdict-demotion S4 acceptance slice.

Mandate-12 criterion 1: every domain noun the S4 Gherkin names is expressed
once here as a typed enum / NewType. Step bodies and the composition service
consume these typed parameters -- no raw ``str`` where a domain enum exists.

S4 demotes the feature-end deep-review verdict hash from "HMAC-signed under the
reviewer key" to "deterministic content hash over the verdict"
(``feature_end_sign_service``). The anti-theater invariant -- refuse to mint
when the reviewer is unnamed or the verdict is unknown/missing -- is preserved
keylessly; the key-unresolvable refusal branch is REMOVED (key absence is a
non-event). The post-demotion vocabulary therefore has NO signing-key state worth
a PRESENT value: there is no key at all. The single ``SigningKeyState`` value the
S4 contract pins is ABSENT -- the keyless run the slice asserts.

S1's ``domain_types.py``, S2's ``domain_types_slice_02.py`` and S3's
``domain_types_slice_03.py`` own the carpaccio-gate / producer / DISCUSS-gate
nouns; this S4-suffixed module owns the feature-end-signer nouns so the four
slice modules never collide on a type name (single-source per slice).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "oss-feature-end-demo").
FeatureId = NewType("FeatureId", str)

# A reviewer agent identifier (e.g. "nw-software-crafter-reviewer").
ReviewerAgentId = NewType("ReviewerAgentId", str)

# A feature-end verdict content hash (lowercase hex, a deterministic SHA-256 the
# signer produces over the verdict's canonical signed region post-demotion). 64
# hex chars when genuine -- byte-identical SHAPE to the pre-demotion HMAC, so the
# downstream emitter + the _is_hex64 ledger validation accept it unchanged.
ContentHash = NewType("ContentHash", str)


class DeepReviewVerdict(str, Enum):
    """The reviewer's deep-review decision on a feature-end review.

    APPROVED -- the deep review certified the feature-end is sound.
    REJECTED -- the deep review found the feature-end deficient.

    Both are REAL verdicts the signer seals; the verdict value is one of the
    seven content-hashed fields (it is bound into the produced content hash, so a
    different decision yields a different hash -- tamper-evident keylessly).
    """

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class SealOutcome(str, Enum):
    """The user-observable verdict of one `des feature-end sign` invocation.

    SUCCEEDED -- the signer produced a deterministic content hash over the real
                 deep-review verdict and reported success (exit zero).
    REFUSED   -- the signer refused (non-zero exit) because the anti-theater
                 invariant was violated -- no named reviewer or an unknown /
                 missing verdict -- so NO hash was produced. Post-demotion the
                 refusal is NEVER a missing-key refusal: key absence is a
                 non-event.
    """

    SUCCEEDED = "succeeded"
    REFUSED = "refused"


class SigningKeyState(str, Enum):
    """Whether a reviewer signing key is present in the environment.

    ABSENT  -- neither the env var nor the key file is present. Post-demotion
               this is the ONLY state the S4 contract exercises: a real verdict
               still seals (key absence is a non-event), and a non-real verdict
               still refuses for the anti-theater reason, NEVER for a missing key.
    """

    ABSENT = "absent"


@dataclass(frozen=True)
class DeepReviewRecord:
    """A REAL deep-review verdict record the signer content-hashes (never mints).

    Carries the reviewer's actual decision -- the agent that reviewed and the
    APPROVED/REJECTED verdict. This is the input the anti-theater invariant
    requires: a seal request with no named reviewer or an unknown/missing verdict
    is REFUSED.

    The hashed region reuses the ``des.domain.at_review_signing`` SSOT's seven
    SIGNED_FIELDS; post-demotion the signer produces
    ``sha256(canonical_signed_json(record, SIGNED_FIELDS))`` of this record. The
    test recomputes the same content hash independently (KEYLESSLY) to assert the
    produced hash is a GENUINE content hash over THIS input, not a minted constant.
    """

    feature_id: FeatureId
    reviewer_agent_id: ReviewerAgentId
    verdict: DeepReviewVerdict
    findings: tuple[str, ...] = field(default_factory=tuple)


# NOTE on the anti-theater refusal matrix (empty-agent / unknown-verdict /
# missing-verdict): those refusals are RETAINED unchanged by S4 -- at tip the
# signer already checks the real-verdict preconditions BEFORE it resolves a key,
# so they are ALREADY keyless and fire for the anti-theater reason today. They
# are NOT re-pinned by an S4 active-RED scenario (they would pass at tip -- not
# missing functionality); they stay witnessed keylessly by the re-authored
# residue of the oss-feature-end-emit-cli slice-02 producer suite (feature-delta
# S4 supersede inventory). No MalformedVerdictKind enum lives here -- the S4
# contract is the two genuinely-changed behaviors only (keyless content hash +
# key-absence-non-event).
