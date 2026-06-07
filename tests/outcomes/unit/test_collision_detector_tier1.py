"""Unit test: CollisionDetector Tier-1 — exact normalized shape tuple match.

Driving port: CollisionDetector.check(target_shape, registry_snapshot).
Tier-2 (Jaccard) deferred to step 02-01; this step asserts the stub
returns an empty tuple for tier2_matches.
"""

from __future__ import annotations

import pytest
from nwave_ai.outcomes.application.collision_detector import (
    CollisionDetector,
    TargetShape,
)
from nwave_ai.outcomes.domain.outcome import InputShape, Outcome, OutputShape


def _outcome(id_: str, input_shape: str, output_shape: str) -> Outcome:
    return Outcome(
        id=id_,
        kind="specification",
        summary="",
        feature="f",
        inputs=(InputShape(shape=input_shape),),
        output=OutputShape(shape=output_shape),
        keywords=(),
        artifact="",
        related=(),
        superseded_by=None,
    )


@pytest.mark.parametrize(
    "registered_input,registered_output,target_input,target_output,expected_matches",
    [
        # Exact normalized match — collision.
        (
            "FeatureDeltaModel",
            "tuple[Violation, ...]",
            "FeatureDeltaModel",
            "tuple[Violation, ...]",
            ("OUT-A",),
        ),
        # Whitespace differences normalized away — still collides.
        (
            "(text: str, file_path: str)",
            "tuple[Violation, ...]",
            "(text:str,file_path:str)",
            "tuple[Violation,...]",
            ("OUT-A",),
        ),
        # Different input shape — no collision.
        (
            "FeatureDeltaModel",
            "tuple[Violation, ...]",
            "OtherModel",
            "tuple[Violation, ...]",
            (),
        ),
        # Different output shape — no collision.
        (
            "FeatureDeltaModel",
            "tuple[Violation, ...]",
            "FeatureDeltaModel",
            "str",
            (),
        ),
    ],
)
def test_tier1_exact_normalized_shape_match(
    registered_input: str,
    registered_output: str,
    target_input: str,
    target_output: str,
    expected_matches: tuple[str, ...],
) -> None:
    detector = CollisionDetector()
    snapshot = (_outcome("OUT-A", registered_input, registered_output),)
    target = TargetShape(input_shape=target_input, output_shape=target_output)

    report = detector.check(target=target, snapshot=snapshot)

    assert report.tier1_matches == expected_matches
    # Tier-2 is a stub for this step — must always be empty.
    assert report.tier2_matches == ()
