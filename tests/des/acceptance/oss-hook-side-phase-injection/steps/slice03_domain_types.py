"""Domain types for slice-03 -- mechanical HMAC trailer projection.

slice-03 of oss-hook-side-phase-injection (the DISTILL-wave hook keystone, D1).
Every domain noun in the slice-03 Gherkin is expressed once here as a typed enum
or NewType; step bodies and the composition service consume these typed
parameters (Mandate-12 criterion 1 -- domain types module exists with typed
enums for every domain noun used in Gherkin).

slice-03 covers ONE new driving surface: the ``derive_review_trailer`` CLI -- an
orchestrator-invoked ledger projection (NOT a hook, NOT a commit hook). It reads
a signed ``ATReviewVerdict`` ledger record and projects the verifier's EXACTLY
four-field canonical verdict (``verdict``, ``timestamp``, ``reviewer_agent_id``
from the record's signed region; ``findings_summary`` from its unsigned region),
REUSING ``verify_commit_trailers.canonical_verdict_json`` (the verifier's own
serializer = SSOT for what U2 recomputes -- NOT the producer's 7-field
``canonical_at_review_json``, which is over an INCOMPATIBLE key set). It emits
BOTH a ``Reviewed-by: <agent>:<hmac>`` line AND the matching
``Verdict-Payload: {<4-field canonical JSON>}`` line for the orchestrator to
embed in the slice commit message it is already authoring.

The single-serializer invariant -- derive and verify share
``canonical_verdict_json`` -- is the mechanical anti-drift guard. AT-2's
derive->verify round-trip IS that guard: a field-set drift or a signing-key
mismatch is structurally un-representable in a GREEN round-trip.

HARD INVARIANT (NOT a hook): the derive CLI only READS the ledger record and
PROJECTS the trailer pair to stdout. It never mutates the ledger, never spawns an
agent, never touches the commit lifecycle. The orchestrator embeds the lines; the
existing git-side ``verify_commit_trailers`` (U2) is the fail-closed check.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "atdd-pure-demo").
FeatureId = NewType("FeatureId", str)

# A carpaccio slice identifier (e.g. "slice-01").
SliceId = NewType("SliceId", str)


class TrailerProjection(str, Enum):
    """The user-observable shape of the derived trailer pair (AT-1).

    PAIR_EMITTED -- the derive CLI read a signed ``ATReviewVerdict`` and emitted
                    BOTH a ``Reviewed-by: <agent>:<hmac>`` line AND a matching
                    ``Verdict-Payload: {...}`` line over the verifier's 4-field
                    ``canonical_verdict_json``. This is the only success shape:
                    an unpaired ``Reviewed-by`` (no payload) is NEVER valid.
    ABSENT       -- the derive CLI emitted no trailer pair (a wrong-path signal
                    AT-1 asserts against -- a signed record must always project a
                    complete pair).
    """

    PAIR_EMITTED = "pair-emitted"
    ABSENT = "absent"


class RoundTripVerdict(str, Enum):
    """The user-observable verdict of the derive->verify round-trip (AT-2/AT-3).

    VERIFIES        -- the orchestrator embedded the derived pair and the git-side
                       ``verify_commit_trailers`` recomputed the SAME 4-field
                       ``canonical_verdict_json`` and matched the HMAC -- exit 0.
                       Structurally impossible under the old 7-field spec; GREEN
                       only because derive and verify share one serializer.
    HASH_MISMATCH   -- the verifier recomputed a DIFFERENT HMAC over an in-shape
                       4-field payload (a signing-key mismatch between derive-time
                       and verify-time) -- exit 4. The HMAC inputs are well-formed
                       but the signature does not match. Never a silent pass.
    MALFORMED_PAIR  -- the verifier could not even recompute a comparable HMAC
                       because the trailer/payload pair is mal-shaped -- exit 6.
                       Two distinct causes both land here per the SHIPPED verifier:
                       (1) the embedded ``Verdict-Payload`` carries an extra /
                       missing key, so ``canonical_verdict_json`` RAISES on the
                       4-field-strict shape check (verify_commit_trailers.py:86-93,
                       caught at :230-232 -> exit 6); (2) a ``Reviewed-by`` line
                       carries no paired ``Verdict-Payload`` (trailer/payload count
                       mismatch -> exit 6). Never a silent pass.
    """

    VERIFIES = "verifies"
    HASH_MISMATCH = "hash-mismatch"
    MALFORMED_PAIR = "malformed-pair"


class TrailerFault(str, Enum):
    """The fault injected into the derive->verify round-trip (AT-3: C6 negative).

    KEY_MISMATCH    -- the verifier is given a DIFFERENT signing key than the
                       derive side used; the recomputed HMAC over the SAME in-shape
                       4-field payload differs -> exit 4 (HASH_MISMATCH leaf).
    EXTRA_FIELD     -- the embedded ``Verdict-Payload`` is mutated to carry an
                       extra key; the verifier's 4-field-strict
                       ``canonical_verdict_json`` RAISES on the shape check before
                       any HMAC compare -> exit 6 (MALFORMED_PAIR leaf, cause:
                       shape divergence -- NOT a hash mismatch; an extra key is a
                       SHAPE violation the shipped verifier adjudicates as
                       malformed, never as a signature failure).
    UNPAIRED_TRAILER
                    -- the ``Reviewed-by`` line is embedded WITHOUT its matching
                       ``Verdict-Payload`` line -> exit 6 (MALFORMED_PAIR leaf,
                       cause: trailer/payload count mismatch).
    """

    KEY_MISMATCH = "key-mismatch"
    EXTRA_FIELD = "extra-field"
    UNPAIRED_TRAILER = "unpaired-trailer"


# Gherkin-phrase -> typed-value lookups (Mandate-12 criterion 3: no control flow
# in step bodies -- each body is a single typed lookup + composition call).

# The round-trip verdict expected per Gherkin fault phrase for AT-3. Each fault
# maps to exactly one fail-closed verdict -- the closed error set of the
# derive->verify round-trip (C6c: no other outcome escapes).
ROUND_TRIP_VERDICT_BY_FAULT_PHRASE: dict[str, RoundTripVerdict] = {
    "the verifier is given a different signing key": RoundTripVerdict.HASH_MISMATCH,
    "an extra field is added to the embedded verdict payload": (
        RoundTripVerdict.MALFORMED_PAIR
    ),
    "the reviewer line is embedded without its matching verdict payload": (
        RoundTripVerdict.MALFORMED_PAIR
    ),
}

# The fault to inject per Gherkin fault phrase (AT-3 enumerates the three
# materially-distinct ways the round-trip fails closed: C6 negative paths).
FAULT_BY_PHRASE: dict[str, TrailerFault] = {
    "the verifier is given a different signing key": TrailerFault.KEY_MISMATCH,
    "an extra field is added to the embedded verdict payload": (
        TrailerFault.EXTRA_FIELD
    ),
    "the reviewer line is embedded without its matching verdict payload": (
        TrailerFault.UNPAIRED_TRAILER
    ),
}

# The verifier exit code expected per round-trip verdict (the closed error set
# of the git-side U2 check: 0 ok | 4 hash mismatch | 6 malformed/unpaired).
EXIT_CODE_BY_VERDICT: dict[RoundTripVerdict, int] = {
    RoundTripVerdict.VERIFIES: 0,
    RoundTripVerdict.HASH_MISMATCH: 4,
    RoundTripVerdict.MALFORMED_PAIR: 6,
}
