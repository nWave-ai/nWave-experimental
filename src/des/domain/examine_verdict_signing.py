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
import re

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


# The append-only Session-log heading nw-user-examiner writes to the SAME
# charter after a verdict is recorded (its normal LOG + REPORT step). The seal
# must exclude everything from this heading onward -- see ``charter_seal``.
#
# The scaffold/template emit ``## Session log (append-only)`` verbatim, but
# hand-authored charters use spelling variants (``## Session Log`` capital-L,
# ``## Session log`` without the ``(append-only)`` suffix -- 35/200 checked-in
# charters as of 2026-07-20). A literal-string exclusion silently fails for
# those, so the examiner's own append stales a genuine PASS. This tolerant
# matcher exempts every real spelling: a Markdown heading line (``##`` or more)
# whose text starts with "session log" (case-insensitive), suffix optional.
# It matches the canonical heading at the SAME byte offset as the prior literal
# ``str.partition`` did, so already-recorded seals stay valid by construction.
_SESSION_LOG_HEADING_RE = re.compile(
    r"^#{2,}[ \t]*session[ \t]+log\b", re.IGNORECASE | re.MULTILINE
)


def charter_seal(charter_bytes: bytes) -> str:
    """SHA-256 content-seal over a charter file's SUBSTANCE bytes.

    The tamper-evidence primitive: recomputing this over the charter's CURRENT
    bytes and comparing against a recorded seal is how the commit-time gate
    detects a charter that changed after examination (stale-seal, void).

    Excludes the append-only ``## Session log`` section: nw-user-examiner
    appends one row there per exam as its normal LOG + REPORT step, and that
    append must not itself void the verdict it just recorded. Everything
    BEFORE the first Session-log heading is substance (Intent/Preconditions/
    Charter/Expected observations) and still seals -- a genuine edit there
    must still change the seal. The heading match tolerates real spelling
    variants (case + optional ``(append-only)`` suffix); absent a Session-log
    heading the FULL text seals (backward-compatible).
    """
    text = charter_bytes.decode("utf-8")
    match = _SESSION_LOG_HEADING_RE.search(text)
    substance = text[: match.start()] if match else text
    return hashlib.sha256(substance.encode("utf-8")).hexdigest()


def charter_seal_matches(charter_bytes: bytes, recorded_seal: str) -> bool:
    """True iff the CURRENT charter bytes still match the recorded seal."""
    return charter_seal(charter_bytes) == recorded_seal
