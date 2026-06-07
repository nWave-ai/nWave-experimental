"""Unit test: Outcome value object — immutability + tuple-typed collections.

Driving port: the Outcome dataclass IS its own driving port (pure value
object, public constructor signature is the contract).
"""

from __future__ import annotations

import pytest
from nwave_ai.outcomes.domain.outcome import InputShape, Outcome, OutputShape


def _make_outcome() -> Outcome:
    return Outcome(
        id="OUT-A",
        kind="specification",
        summary="Walking skeleton outcome",
        feature="outcomes-registry",
        inputs=(InputShape(shape="FeatureDeltaModel"),),
        output=OutputShape(shape="tuple[Violation, ...]"),
        keywords=("non-empty", "required"),
        artifact="nwave_ai/outcomes/walking_skeleton.py",
        related=(),
        superseded_by=None,
    )


def test_outcome_is_frozen_and_uses_tuples() -> None:
    """Outcome is immutable; collections are tuples (Object Calisthenics
    Rule 4 — first-class collections, immutable)."""
    outcome = _make_outcome()

    # Frozen: assignment raises FrozenInstanceError (subclass of AttributeError).
    import dataclasses

    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        outcome.id = "OUT-B"  # type: ignore[misc]

    # Collections are tuples (immutable), not lists.
    assert isinstance(outcome.inputs, tuple)
    assert isinstance(outcome.keywords, tuple)
    assert isinstance(outcome.related, tuple)

    # Field values preserved.
    assert outcome.id == "OUT-A"
    assert outcome.kind == "specification"
    assert outcome.inputs[0].shape == "FeatureDeltaModel"
    assert outcome.output.shape == "tuple[Violation, ...]"
