"""L1.4 verdict-input-digest — pure 3-input freshness key, no I/O.

The L1.4 contract pins the digest:

    SHA256(json.dumps({"wheel": h1, "e2e_files": h2, "ci_job_closure": h3},
                       sort_keys=True))

Each input is itself a SHA256 over the relevant bytes. This module hashes the
already-computed component digests; the CLI computes them from file bytes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class VerdictInputBreakdown:
    """The three component hashes feeding the verdict-input digest (L1.4)."""

    wheel: str
    e2e_files: str
    ci_job_closure: str


def compute_verdict_input_digest(breakdown: VerdictInputBreakdown) -> str:
    """Return the SHA256 of the canonical-JSON of the 3-input breakdown."""
    canonical = json.dumps(asdict(breakdown), sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


__all__ = ["VerdictInputBreakdown", "compute_verdict_input_digest"]
