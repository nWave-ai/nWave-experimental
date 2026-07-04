"""ExamineVerdict content-seal helpers -- mirrors ``at_review_signing`` (P1.2).

evolution-plan P1.2 (User-Examiner spine wiring): the per-slice commit gate
requires a recorded ``ExamineVerdict`` -- a human-intent charter walked through
the REAL surface by ``nw-user-examiner``, verdict observed -- before a slice may
commit. This module is the ONE tamper-evidence SSOT the producer
(``des.cli.record_examine_verdict``) and the consumer (``des.cli.commit_slice``)
both depend on, mirroring the ``at_review_signing`` pattern exactly: a canonical
JSON serializer over a fixed signed-field tuple, plus a content-seal so a
hand-edited ``.jsonl`` line cannot forge a PASS.

Two content seals compose here, deliberately kept distinct:

* ``charter_seal`` -- a SHA-256 over the CHARTER FILE's raw bytes at exam time.
  This is the tamper-evidence a hand-edited charter cannot survive: the
  commit-time gate recomputes the seal over the charter's CURRENT bytes and
  refuses (stale-seal, void) on any mismatch.
* ``canonical_examine_json`` -- the ONE canonicalizer (reusing
  ``des.domain.at_review_signing.canonical_signed_json``, the O-5 SSOT
  serializer) over the record's own signed fields, for parity with the
  ``ATReviewVerdict`` pattern and any future record-level seal.

Stdlib-only (no third-party imports) so the module is bundle-safe.
"""

from __future__ import annotations

import hashlib

from des.domain.at_review_signing import canonical_signed_json


# The examine-verdict record's signed fields, in declaration order -- mirrors
# ``SIGNED_FIELDS`` in ``at_review_signing`` (ADR-029 D5 pattern). ``event`` is
# excluded (the canonical serializer sorts keys and signs exactly this tuple).
EXAMINE_SIGNED_FIELDS: tuple[str, ...] = (
    "schema_version",
    "feature_id",
    "slice_id",
    "charter_path",
    "verdict",
    "observations",
    "charter_seal",
    "examiner",
    "timestamp",
)

# The three closed verdict values ``des record-examine-verdict`` accepts.
EXAMINE_VERDICTS: tuple[str, ...] = ("PASS", "FAIL", "INDETERMINATE")


def canonical_examine_json(record: dict[str, object]) -> bytes:
    """Serialize EXACTLY the ``EXAMINE_SIGNED_FIELDS`` of ``record`` to canonical JSON.

    O-5: byte-identical composition of ``canonical_signed_json`` (the ONE
    canonicalizer every signed record in this codebase reuses) with the
    examine-verdict field tuple.
    """
    return canonical_signed_json(record, EXAMINE_SIGNED_FIELDS)


def charter_seal(charter_bytes: bytes) -> str:
    """SHA-256 content-seal over a charter file's raw bytes.

    The tamper-evidence primitive: recomputing this over the charter's CURRENT
    bytes and comparing against a recorded seal is how the commit-time gate
    detects a charter that changed after examination (stale-seal, void).
    """
    return hashlib.sha256(charter_bytes).hexdigest()


def charter_seal_matches(charter_bytes: bytes, recorded_seal: str) -> bool:
    """True iff the CURRENT charter bytes still match the recorded seal."""
    return charter_seal(charter_bytes) == recorded_seal
