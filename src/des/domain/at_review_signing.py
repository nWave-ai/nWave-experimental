"""ATReviewVerdict HMAC signing contract -- the ONE SSOT (ADR-029 D5, AD-05).

The signed region of an ``ATReviewVerdict`` record is the seven fields
``schema_version``, ``slice_id``, ``verdict``, ``reviewer_agent_id``,
``at_ids``, ``at_content_hash``, ``timestamp``. ``event``, ``hmac_sha256`` and
``findings_summary`` are EXCLUDED from the signed input.

Before this module the canonical serializer + signing-key resolution + the
signed-field set lived duplicated byte-for-byte across the PRODUCER
(``des.cli.at_review_verdict``) and the CONSUMER
(``des.cli.carpaccio_slice_gate``). Any one-char divergence in the field set
or canonicalization would silently break verification or weaken tamper-
evidence. Per AD-05 the shared LOGIC must NOT live in ``cli/`` -- it is pure
domain logic (HMAC + canonical JSON), so it is consolidated here. Both CLI
modules import from this SSOT; the local definitions are deleted.

Stdlib-only (no third-party imports) so the module is bundle-safe.

Byte-preservation invariant: the canonical JSON serialization and HMAC
computation produced here are byte-identical to the pre-consolidation cli/
copies (same field set, same sort/separators, same key resolution + env/file
precedence). A refactor that changes the signed bytes breaks every
previously-signed verdict -- this module exists precisely so that contract
lives in one place and cannot drift.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


# ADR-029 D5 B1: the seven HMAC-signed fields, in declaration order. The
# canonical serializer sorts keys, so ``event``, ``hmac_sha256`` and
# ``findings_summary`` are simply absent from the signed payload.
SIGNED_FIELDS: tuple[str, ...] = (
    "schema_version",
    "slice_id",
    "verdict",
    "reviewer_agent_id",
    "at_ids",
    "at_content_hash",
    "timestamp",
)

# Reviewer signing-key resolution precedence: env var first, then key file.
SIGNING_KEY_ENV = "NWAVE_REVIEWER_SIGNING_KEY"
SIGNING_KEY_FILE = ".nwave/secrets/reviewer-signing.key"


def canonical_at_review_json(record: dict[str, object]) -> bytes:
    """Serialize the seven signed fields of an ATReviewVerdict to canonical JSON.

    ADR-029 D5 B1: ``json.dumps`` over EXACTLY the seven signed fields with
    sorted keys and no whitespace, UTF-8 encoded. ``event``, ``hmac_sha256``
    and ``findings_summary`` are NOT part of the signed input.
    """
    signed = {field: record[field] for field in SIGNED_FIELDS}
    return json.dumps(signed, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_verdict_hmac(record: dict[str, object], key: bytes) -> str:
    """Compute HMAC-SHA256 over ``canonical_at_review_json(record)`` as hex."""
    return hmac.new(key, canonical_at_review_json(record), hashlib.sha256).hexdigest()


def load_signing_key(repo_root: Path) -> bytes | None:
    """Resolve the reviewer signing key: env first, file fallback.

    Returns ``None`` when neither the env var nor the key file is present --
    callers that must fail-closed (the consumer gate) branch on ``None``;
    callers that must have a key to sign (the producer) wrap this via
    :func:`require_signing_key`.
    """
    env_value = os.environ.get(SIGNING_KEY_ENV)
    if env_value:
        return env_value.encode("utf-8")
    key_file = repo_root / SIGNING_KEY_FILE
    if key_file.is_file():
        return key_file.read_bytes().strip()
    return None


def require_signing_key(repo_root: Path) -> bytes:
    """Resolve the reviewer signing key, raising when unresolvable.

    The PRODUCER must have a key to sign with -- an unresolvable key is an
    ``AssertionError`` (byte-identical message to the pre-consolidation
    producer copy), not a ``None`` the producer would have to re-check.
    """
    key = load_signing_key(repo_root)
    if key is None:
        raise AssertionError(
            "reviewer signing key unresolvable: set NWAVE_REVIEWER_SIGNING_KEY or "
            f"provide {SIGNING_KEY_FILE}"
        )
    return key
