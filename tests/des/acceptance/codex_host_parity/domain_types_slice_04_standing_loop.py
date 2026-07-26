"""Slice-04 acceptance vocabulary for the standing-loop operator outcome.

DISTILL-time placeholder: when DELIVER lands the standing-loop production types,
these declarations must move to production and this module must import them
directly.  It must not remain a structurally independent duplicate.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ContinuedWork:
    """Operator-declared continuation and its bounded execution context."""

    project_root: Path
    outcome: str
    context_mode: str
    max_tokens_per_tick: int
    max_wall_seconds: int
    max_agent_concurrency: int
    max_box_concurrency: int
    continuity_proof_id: str | None = None


@dataclass(frozen=True)
class ManualOccurrence:
    """One operator-authorised manual semantic occurrence."""

    loop_id: str
    idempotency_key: str
