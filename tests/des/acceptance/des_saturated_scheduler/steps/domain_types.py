"""DISTILL-time scheduler nouns; DELIVER must replace these with production imports.

This module is a placeholder until DELIVER lands the scheduler's production
types. In that same GREEN slice, the declarations move to production and this
module imports them directly; it must not remain an independent mirror.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NewType


FeatureId = NewType("FeatureId", str)
PolicyDigest = NewType("PolicyDigest", str)


@dataclass(frozen=True)
class CommandObservation:
    """Port-exposed result captured from one real DES dispatcher invocation."""

    exit_code: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class SchedulerRun:
    """The two fresh plan reads plus the immutable pre-read workspace bytes."""

    first: CommandObservation
    second: CommandObservation
    feature_delta_before: bytes
    evidence_before: bytes | None
