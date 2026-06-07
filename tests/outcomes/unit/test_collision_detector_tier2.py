"""Unit test: CollisionDetector verdict matrix (Tier-1 + Tier-2).

Driving port: ``CollisionDetector.check(target, snapshot)``. The detector
combines Tier-1 (exact normalized shape) with Tier-2 (keyword Jaccard
>= 0.4 threshold) into a single verdict per the DESIGN spec matrix:

  | Tier-1 fires | Tier-2 >= 0.4 | Verdict     |
  | YES          | YES           | collision   |
  | YES          | NO            | ambiguous   |
  | NO           | YES           | ambiguous   |
  | NO           | NO            | clean       |

Tier-2 matches are reported with their Jaccard score for observability.
"""

from __future__ import annotations

import pytest
from nwave_ai.outcomes.application.collision_detector import (
    CollisionDetector,
    TargetShape,
)
from nwave_ai.outcomes.domain.outcome import InputShape, Outcome, OutputShape


def _outcome(
    id_: str,
    input_shape: str,
    output_shape: str,
    keywords: tuple[str, ...] = (),
) -> Outcome:
    return Outcome(
        id=id_,
        kind="specification",
        summary="",
        feature="f",
        inputs=(InputShape(shape=input_shape),),
        output=OutputShape(shape=output_shape),
        keywords=keywords,
        artifact="",
        related=(),
        superseded_by=None,
    )


@pytest.mark.parametrize(
    (
        "registered_input,registered_output,registered_keywords,"
        "target_input,target_output,target_keywords,"
        "expected_verdict,expected_tier1,expected_tier2_id"
    ),
    [
        # Tier-1 YES + Tier-2 YES (identical keywords) -> collision
        (
            "FeatureDeltaModel",
            "tuple[Violation, ...]",
            ("cherry-pick", "row-count"),
            "FeatureDeltaModel",
            "tuple[Violation, ...]",
            ("cherry-pick", "row-count"),
            "collision",
            ("OUT-A",),
            "OUT-A",
        ),
        # Tier-1 YES + Tier-2 NO (disjoint keywords) -> ambiguous
        (
            "(text: str, file_path: str)",
            "tuple[Violation, ...]",
            ("section", "heading", "wave", "format"),
            "(text: str, file_path: str)",
            "tuple[Violation, ...]",
            ("column", "ddd", "table", "header"),
            "ambiguous",
            ("OUT-A",),
            None,
        ),
        # Tier-1 NO + Tier-2 YES (different shapes, identical keywords) -> ambiguous
        (
            "ModelOne",
            "tuple[Violation, ...]",
            ("cherry-pick", "row-count"),
            "ModelTwo",
            "str",
            ("cherry-pick", "row-count"),
            "ambiguous",
            (),
            "OUT-A",
        ),
        # Tier-1 NO + Tier-2 NO -> clean
        (
            "ModelOne",
            "tuple[Violation, ...]",
            ("alpha", "beta"),
            "ModelTwo",
            "str",
            ("totally", "different"),
            "clean",
            (),
            None,
        ),
    ],
)
def test_verdict_matrix(
    registered_input: str,
    registered_output: str,
    registered_keywords: tuple[str, ...],
    target_input: str,
    target_output: str,
    target_keywords: tuple[str, ...],
    expected_verdict: str,
    expected_tier1: tuple[str, ...],
    expected_tier2_id: str | None,
) -> None:
    detector = CollisionDetector()
    snapshot = (
        _outcome(
            "OUT-A",
            registered_input,
            registered_output,
            keywords=registered_keywords,
        ),
    )
    target = TargetShape(
        input_shape=target_input,
        output_shape=target_output,
        keywords=target_keywords,
    )

    report = detector.check(target=target, snapshot=snapshot)

    assert report.verdict == expected_verdict
    assert report.tier1_matches == expected_tier1
    if expected_tier2_id is None:
        assert report.tier2_matches == ()
    else:
        assert len(report.tier2_matches) == 1
        match_id, match_score = report.tier2_matches[0]
        assert match_id == expected_tier2_id
        assert match_score >= 0.4
