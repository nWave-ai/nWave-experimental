"""CollisionDetector — Tier-1 + Tier-2 verdict pipeline.

Tier-1: exact normalized shape match (``input_shape``, ``output_shape``).
Tier-2: keyword Jaccard similarity ``>= 0.4``.

Verdict matrix (per DESIGN spec):

    | Tier-1 fires | Tier-2 >= 0.4 | Verdict   |
    | YES          | YES           | collision |
    | YES          | NO            | ambiguous |
    | NO           | YES           | ambiguous |
    | NO           | NO            | clean     |
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from nwave_ai.outcomes.domain.jaccard import score, tokenize
from nwave_ai.outcomes.domain.outcome import Outcome  # noqa: TC001  # runtime
from nwave_ai.outcomes.domain.shape import normalize_shape


_TIER2_THRESHOLD = 0.4


Verdict = Literal["clean", "collision", "ambiguous"]


@dataclass(frozen=True)
class TargetShape:
    """The shape + keywords the author wants to register."""

    input_shape: str
    output_shape: str
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class CollisionReport:
    """Result of a collision check (Tier-1 + Tier-2 + verdict)."""

    tier1_matches: tuple[str, ...]
    tier2_matches: tuple[tuple[str, float], ...] = field(default_factory=tuple)
    verdict: Verdict = "clean"


class CollisionDetector:
    """Detect collisions between a target shape and the registry snapshot."""

    def check(
        self,
        target: TargetShape,
        snapshot: tuple[Outcome, ...],
    ) -> CollisionReport:
        """Return Tier-1 IDs, Tier-2 (id, score) pairs, and a verdict."""
        tier1 = _tier1_matches(target, snapshot)
        tier2 = _tier2_matches(target, snapshot)
        return CollisionReport(
            tier1_matches=tier1,
            tier2_matches=tier2,
            verdict=_verdict(bool(tier1), bool(tier2)),
        )


def _tier1_matches(
    target: TargetShape, snapshot: tuple[Outcome, ...]
) -> tuple[str, ...]:
    """Return ids of outcomes whose normalized (input, output) tuple equals target."""
    target_tuple = (
        normalize_shape(target.input_shape),
        normalize_shape(target.output_shape),
    )
    return tuple(o.id for o in snapshot if _shape_tuple(o) == target_tuple)


def _tier2_matches(
    target: TargetShape, snapshot: tuple[Outcome, ...]
) -> tuple[tuple[str, float], ...]:
    """Return (id, rounded_score) pairs for outcomes meeting Tier-2 threshold."""
    target_tokens = _tokens_for(target.keywords)
    return tuple(
        (o.id, _round_score(s))
        for o, s in (
            (o, score(_tokens_for(o.keywords), target_tokens)) for o in snapshot
        )
        if s >= _TIER2_THRESHOLD
    )


def _verdict(tier1_fired: bool, tier2_fired: bool) -> Verdict:
    """Map (Tier-1, Tier-2) firing flags to a verdict."""
    if tier1_fired and tier2_fired:
        return "collision"
    if tier1_fired or tier2_fired:
        return "ambiguous"
    return "clean"


def _shape_tuple(outcome: Outcome) -> tuple[str, str]:
    """Canonical (input, output) tuple for the first input shape."""
    if not outcome.inputs:
        return ("", normalize_shape(outcome.output.shape))
    return (
        normalize_shape(outcome.inputs[0].shape),
        normalize_shape(outcome.output.shape),
    )


def _tokens_for(keywords: tuple[str, ...]) -> frozenset[str]:
    """Tokenise a tuple of keyword fragments into a single set."""
    if not keywords:
        return frozenset()
    return tokenize(" ".join(keywords))


def _round_score(value: float) -> float:
    """Round Jaccard score to 2 decimals for stable stdout/reporting."""
    return round(value, 2)
