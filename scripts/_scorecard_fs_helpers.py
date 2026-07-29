"""Shared filesystem predicates for the beta-scorecard GOAL CONTRACT scripts.

Extracted 2026-07-29 (cleanup pass) -- `scripts/beta_consolidation_scorecard.py`
and `scripts/beta_readiness_scorecard.py` each carried a byte-identical copy of
`REPO` / `_file_exists` / `_file_contains` (verified via `diff` before this
extraction). One definition, two importers -- no behavior change; each script's
own predicates and CLI remain untouched.

Pure stdlib only (target-machine independence, matches both callers' own
"no git, no external packages" constraint).
"""

from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parent.parent


def file_exists(rel: str) -> bool:
    return (REPO / rel).is_file()


def file_contains(rel: str, needle: str) -> bool:
    path = REPO / rel
    if not path.is_file():
        return False
    try:
        return needle in path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
