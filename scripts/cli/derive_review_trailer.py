"""Reviewer-trailer projection CLI (friction #35 closure -- slice-03).

WHY-NEW-FILE: scripts/cli/derive_review_trailer.py
  CLOSEST-EXISTING: src/des/cli/at_review_verdict.py
  EXTENSION-COST: at_review_verdict is the PRODUCER that signs + writes the
    7-field ATReviewVerdict record via canonical_at_review_json; folding the
    projection in would couple the producer's 7-field signed region to the
    verifier's INCOMPATIBLE 4-field canonical_verdict_json on one module.
  PARALLEL-RATIONALE: derive READS a recorded verdict and re-serialises it over
    the verifier's 4-field serializer (a different, incompatible key set) -- it
    must REUSE des.cli.verify_commit_trailers.canonical_verdict_json, not the
    producer's serializer, so its dependency surface is the verifier, not the
    producer.

This CLI is an orchestrator-invoked ledger projection -- NOT a hook, NOT a commit
hook. It reads the slice's signed ``ATReviewVerdict`` record from the AT-completion
ledger and projects the verifier's EXACTLY-four-field canonical verdict
(``verdict``, ``timestamp``, ``reviewer_agent_id`` from the record's signed region;
``findings_summary`` from its unsigned region).

It REUSES ``des.cli.verify_commit_trailers.canonical_verdict_json`` +
``compute_verdict_hash`` -- the verifier's OWN serializer is the SSOT for what the
git-side U2 check recomputes (NOT the producer's 7-field ``canonical_at_review_json``,
which is over an incompatible key set: ``verify_commit_trailers.canonical_verdict_json``
RAISES on any extra/missing key). Derive and verify therefore share ONE serializer --
the single-serializer anti-drift invariant -- so a GREEN derive->verify round-trip is
structurally impossible under any field-set drift.

It emits BOTH lines to stdout for the orchestrator to embed in the slice commit:

    Reviewed-by: <reviewer_agent_id>:<hmac-sha256-hex>
    Verdict-Payload: {<4-field canonical JSON>}

The verifier needs one ``Verdict-Payload`` per ``Reviewed-by`` (else exit 6), so the
pair is always emitted together.

HARD INVARIANT (NOT a hook): this CLI only READS the ledger record and PROJECTS the
trailer pair to stdout. It never mutates the ledger, never spawns an agent, never
touches the commit lifecycle.

Stdlib + des-runtime only (no third-party imports) so the module is bundle-safe.

Exit codes:
    0 = a signed ATReviewVerdict was found and the trailer pair was projected
    3 = no signed ATReviewVerdict record for the requested (feature_id, slice_id)
    5 = signing key unresolvable (env unset + file absent)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli.verify_commit_trailers import (
    DEFAULT_KEY_ENV,
    DEFAULT_KEY_FILE,
    canonical_verdict_json,
    compute_verdict_hash,
)


_AT_REVIEW_VERDICT = "ATReviewVerdict"

# The four fields the verifier's canonical_verdict_json signs, in no particular
# order (the serializer sorts keys). ``verdict``, ``timestamp`` and
# ``reviewer_agent_id`` come from the record's signed region; ``findings_summary``
# from its unsigned region (at_review_verdict.py:122).
_PROJECTED_FIELDS: tuple[str, ...] = (
    "verdict",
    "timestamp",
    "reviewer_agent_id",
    "findings_summary",
)


def _load_signing_key(repo_root: Path) -> bytes | None:
    """Resolve the reviewer signing key: env first, file fallback.

    Mirrors ``verify_commit_trailers._load_key`` resolution order so the derive
    side signs with the SAME key the verifier later recomputes against. Returns
    ``None`` when neither the env var nor the key file is present.
    """
    env_value = os.environ.get(DEFAULT_KEY_ENV)
    if env_value:
        return env_value.encode("utf-8")
    key_file = repo_root / DEFAULT_KEY_FILE
    if key_file.is_file():
        file_key: bytes = key_file.read_bytes().strip()
        return file_key
    return None


def _resolve_repo_root(override: str | None) -> Path:
    if override:
        return Path(override)
    env = os.environ.get("NWAVE_REPO_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2]


def _read_signed_verdict(
    repo_root: Path, feature_id: str, slice_id: str
) -> dict[str, object] | None:
    """Read the signed ATReviewVerdict record for ``(feature_id, slice_id)``.

    Reads through the production ``AtCompletionLedger`` reader under its M7
    fail-closed integrity contract. Returns the record dict, or ``None`` when no
    ATReviewVerdict record matches the requested slice.
    """
    ledger = AtCompletionLedger(feature_id, repo_root)
    records = ledger.read_records(slice_id=slice_id, event_type=_AT_REVIEW_VERDICT)
    if not records:
        return None
    # A slice carries at most one ATReviewVerdict; honour the most recent if a
    # re-review ever appended a second.
    latest: dict[str, object] = records[-1]
    return latest


def _project_verdict(record: dict[str, object]) -> dict[str, object]:
    """Project the verifier's 4-field canonical verdict from a ledger record."""
    return {field: record[field] for field in _PROJECTED_FIELDS}


def derive_trailer_pair(
    repo_root: Path, feature_id: str, slice_id: str
) -> tuple[str, str] | None:
    """Derive the ``(Reviewed-by, Verdict-Payload)`` trailer pair for a slice.

    Returns ``None`` when no signed ATReviewVerdict record exists for the slice.
    Raises ``LookupError`` when the signing key is unresolvable so ``main`` can
    map it to exit 5.
    """
    record = _read_signed_verdict(repo_root, feature_id, slice_id)
    if record is None:
        return None
    key = _load_signing_key(repo_root)
    if key is None:
        raise LookupError("signing key unresolvable")
    verdict = _project_verdict(record)
    # canonical_verdict_json is the SSOT serializer the verifier recomputes
    # against; reusing it here is the single-serializer anti-drift invariant.
    payload = canonical_verdict_json(verdict).decode("utf-8")
    hmac_hex = compute_verdict_hash(verdict, key)
    reviewed_by = f"Reviewed-by: {record['reviewer_agent_id']}:{hmac_hex}"
    verdict_payload = f"Verdict-Payload: {payload}"
    return reviewed_by, verdict_payload


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="derive_review_trailer",
        description=(
            "Project the reviewer-attribution trailer pair (Reviewed-by + "
            "Verdict-Payload) from a slice's signed ATReviewVerdict ledger "
            "record, reusing the verifier's 4-field canonical serializer."
        ),
        epilog="Exit codes: 0 ok | 3 no signed verdict | 5 missing key.",
    )
    parser.add_argument("--feature-id", required=True)
    parser.add_argument("--slice-id", required=True)
    parser.add_argument("--repo-root", default=None)
    return parser.parse_args(sys.argv[1:] if argv is None else list(argv))


def main(argv: list[str] | None = None) -> int:
    """Project a slice's reviewer-attribution trailer pair to stdout."""
    args = _parse_args(argv)
    repo_root = _resolve_repo_root(args.repo_root)
    try:
        pair = derive_trailer_pair(repo_root, args.feature_id, args.slice_id)
    except LookupError as exc:
        print(f"MISSING KEY: {exc}", file=sys.stderr)
        return 5
    if pair is None:
        diagnostic = {
            "event": "ReviewTrailerProjectionAbsent",
            "feature_id": args.feature_id,
            "slice_id": args.slice_id,
        }
        print(json.dumps(diagnostic, sort_keys=True), file=sys.stderr)
        return 3
    reviewed_by, verdict_payload = pair
    print(reviewed_by)
    print(verdict_payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
