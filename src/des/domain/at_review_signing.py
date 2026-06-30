"""ATReviewVerdict content-seal helpers -- the ONE SSOT (ADR-029 D5, AD-05).

The keyless content-seal substrate: ``canonical_signed_json`` serializes an
``ATReviewVerdict`` record's relevant fields to canonical JSON bytes, used
both by the AT-review verdict producer (for the ``verdict_hash`` content seal)
and by acceptance-test step oracles that recompute the expected hash.

Keyed-HMAC functions and signing-key resolution were removed as part of the
OSS-review-verdict-demotion (oss-hmac-signing-demotion-2026-06-11.md).
The content-seal helpers (``canonical_signed_json``, ``canonical_at_review_json``,
``SIGNED_FIELDS``, ``DISCUSS_SIGNED_FIELDS``) are retained because the
feature-end sign service and AT-step oracles depend on them for the
deterministic keyless content hash.

Stdlib-only (no third-party imports) so the module is bundle-safe.
"""

from __future__ import annotations

import json


# ADR-029 D5 B1: the seven content-seal fields, in declaration order. The
# canonical serializer sorts keys, so ``event``, ``hmac_sha256`` and
# ``findings_summary`` are absent from the sealed payload.
SIGNED_FIELDS: tuple[str, ...] = (
    "schema_version",
    "slice_id",
    "verdict",
    "reviewer_agent_id",
    "at_ids",
    "at_content_hash",
    "timestamp",
)

# O-5 (nwave-flow-v2-enforcement slice-07b, RATIFIED Ale 2026-06-09): the
# DISCUSS-scoped content-seal field set for a ``DiscussReviewVerdict`` record.
# ``event``, ``hmac_sha256`` and ``findings_summary`` are excluded, mirroring
# the ATReviewVerdict exclusions.
DISCUSS_SIGNED_FIELDS: tuple[str, ...] = (
    "schema_version",
    "feature_id",
    "verdict",
    "reviewer_agent_id",
    "feature_delta_hash",
    "timestamp",
)


def canonical_signed_json(record: dict[str, object], fields: tuple[str, ...]) -> bytes:
    """Serialize EXACTLY ``fields`` of ``record`` to canonical JSON bytes.

    The ONE canonicalizer (O-5): ``json.dumps`` over exactly the given signed
    fields with sorted keys, compact separators and UTF-8 encoding. Both the
    AT-review ``SIGNED_FIELDS`` and the DISCUSS ``DISCUSS_SIGNED_FIELDS``
    tuples flow through this single serializer -- one structural truth, two
    field tuples, never a second signing scheme.
    """
    signed = {field: record[field] for field in fields}
    return json.dumps(signed, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_at_review_json(record: dict[str, object]) -> bytes:
    """Serialize the seven signed fields of an ATReviewVerdict to canonical JSON.

    ADR-029 D5 B1: ``json.dumps`` over EXACTLY the seven signed fields with
    sorted keys and no whitespace, UTF-8 encoded. ``event``, ``hmac_sha256``
    and ``findings_summary`` are NOT part of the signed input.

    O-5: byte-identical alias of ``canonical_signed_json(record,
    SIGNED_FIELDS)`` -- the byte-preservation invariant is pinned by the S4
    content-hash oracle in the slice-04 AT
    (``tests/des/acceptance/oss_review_verdict_demotion/steps/composition_slice_04.py``).
    """
    return canonical_signed_json(record, SIGNED_FIELDS)
