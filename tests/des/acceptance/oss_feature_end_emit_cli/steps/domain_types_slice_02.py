"""Domain types for slice-02 -- the `des feature-end sign` CLI.

slice-02 of oss-feature-end-emit-cli (DDD-7 RATIFIED 2026-06-03). Every domain
noun in the slice-02 Gherkin is expressed once here as a typed enum / dataclass
/ NewType; step bodies and the composition service consume these typed
parameters (Mandate-12 criterion 1 -- domain types module exists with typed
enums for every domain noun used in Gherkin).

WHAT SLICE-02 ADDS over slice-01
--------------------------------
slice-01 shipped `des emit-feature-end` -- it CONSUMES a `--verdict-hash` hex
but does NOT produce it. slice-02 ships the PRODUCER: a platform-agnostic
signing use-case (reusing the `des.domain.at_review_signing` SSOT) exposed via
the consolidated `des feature-end sign` shim. The shim takes a REAL deep-review
verdict (agent + APPROVED/REJECTED + findings) and HMACs it -- producing the
hex that feeds `des emit-feature-end --record FeatureEndReviewVerdict
--verdict-hash`.

ANTI-THEATER INVARIANT (load-bearing, DDD-5 + feedback_earned_trust_mechanical_
evidence_not_llm_verdict): the signer NEVER MINTS. It requires the reviewer's
real verdict record and HMACs it via `compute_verdict_hmac(record,
require_signing_key(repo))` over `canonical_at_review_json(record)` -- env
`NWAVE_REVIEWER_SIGNING_KEY`. A sign request with NO real verdict / a
malformed-or-empty verdict record / a missing signing key is REFUSED (exit
non-zero); no hash is produced.

SINGLE ENTRY POINT (DDD-7, AD-26 1:1 mirror): the feature-end subcommands
consolidate under one `des feature-end <verb>` namespace dispatched through the
one `des.cli.__main__` dispatcher + the gate catalog. The consolidated surface
is reachable and slice-01's `emit` still works under it (back-compat preserved).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "oss-feature-end-demo").
FeatureId = NewType("FeatureId", str)

# A reviewer agent identifier (e.g. "nw-software-crafter-reviewer").
ReviewerAgentId = NewType("ReviewerAgentId", str)

# A signed reviewer verdict hash (lowercase hex, an HMAC-SHA256 the signer
# produces from a REAL deep-review verdict). 64 hex chars when genuine.
VerdictHash = NewType("VerdictHash", str)


class DeepReviewVerdict(str, Enum):
    """The reviewer's deep-review decision on a feature-end review.

    APPROVED -- the deep review certified the feature-end is sound.
    REJECTED -- the deep review found the feature-end deficient.

    Both are REAL verdicts the signer will sign; the verdict value is one of the
    seven HMAC-signed fields (it is bound into the produced hash, tamper-evident).
    """

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class SignOutcome(str, Enum):
    """The user-observable verdict of one `des feature-end sign` invocation.

    SUCCEEDED -- the signer produced a signed verdict hash over the real
                 deep-review verdict and reported success (exit zero).
    REFUSED   -- the signer refused (non-zero exit) because the anti-theater
                 invariant was violated -- no real verdict input, a malformed /
                 empty verdict record, or no resolvable signing key -- so NO
                 hash was minted.
    """

    SUCCEEDED = "succeeded"
    REFUSED = "refused"


class FeatureEndVerb(str, Enum):
    """The consolidated `des feature-end <verb>` subcommand surface (DDD-7).

    SIGN -- produce a signed FeatureEndReviewVerdict hash from a real deep-review
            verdict (slice-02, the new surface).
    EMIT -- append a feature-end record to the completion ledger (slice-01's
            behavior, preserved under the consolidated namespace -- back-compat).
    """

    SIGN = "sign"
    EMIT = "emit"


class SigningKeyState(str, Enum):
    """Whether the reviewer signing key is resolvable in the environment.

    PRESENT -- `NWAVE_REVIEWER_SIGNING_KEY` is set; the signer can sign.
    ABSENT  -- neither the env var nor the key file is present; the signer must
               LOUDLY refuse (`require_signing_key` raises), never produce a
               silent unsigned hash.
    """

    PRESENT = "present"
    ABSENT = "absent"


@dataclass(frozen=True)
class DeepReviewRecord:
    """A REAL deep-review verdict record the signer HMACs (never mints).

    Carries the reviewer's actual decision -- the agent that reviewed, the
    APPROVED/REJECTED verdict, and the findings. This is the input the
    anti-theater invariant requires: a sign request with no such real record (or
    an empty / malformed one) is REFUSED.

    The signed region reuses the `des.domain.at_review_signing` SSOT's seven
    SIGNED_FIELDS; the signer produces `compute_verdict_hmac` over
    `canonical_at_review_json` of this record. The test recomputes the same HMAC
    independently to assert the produced hash is a GENUINE signature over THIS
    input, not a minted constant.
    """

    feature_id: FeatureId
    reviewer_agent_id: ReviewerAgentId
    verdict: DeepReviewVerdict
    findings: tuple[str, ...] = field(default_factory=tuple)


class MalformedVerdictKind(str, Enum):
    """The kinds of non-real verdict input the signer must REFUSE (anti-theater).

    Closed enumeration of the refusal-input matrix (C6 negative/robustness): a
    real deep-review verdict has a non-empty agent AND a verdict value the signer
    recognizes. Each kind below violates one of those and yields no hash.

    EMPTY_AGENT       -- the reviewer agent id is empty / whitespace.
    UNKNOWN_VERDICT   -- the verdict value is not APPROVED / REJECTED.
    MISSING_VERDICT   -- no verdict value at all (the decision was never made).
    NO_RECORD         -- no verdict record supplied at all (the bare command).
    """

    EMPTY_AGENT = "empty_agent"
    UNKNOWN_VERDICT = "unknown_verdict"
    MISSING_VERDICT = "missing_verdict"
    NO_RECORD = "no_record"
