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

from dataclasses import dataclass

import pytest
from nwave_ai.outcomes.application.collision_detector import (
    CollisionDetector,
    TargetShape,
)
from nwave_ai.outcomes.domain.outcome import InputShape, Outcome, OutputShape


@dataclass(frozen=True)
class _RegisteredCase:
    input_shape: str
    output_shape: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class _TargetCase:
    input_shape: str
    output_shape: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class _ExpectedOutcome:
    verdict: str
    tier1: tuple[str, ...]
    tier2_id: str | None


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
    ("registered", "target", "expected"),
    [
        pytest.param(
            _RegisteredCase(
                input_shape="FeatureDeltaModel",
                output_shape="tuple[Violation, ...]",
                keywords=("cherry-pick", "row-count"),
            ),
            _TargetCase(
                input_shape="FeatureDeltaModel",
                output_shape="tuple[Violation, ...]",
                keywords=("cherry-pick", "row-count"),
            ),
            _ExpectedOutcome(
                verdict="collision",
                tier1=("OUT-A",),
                tier2_id="OUT-A",
            ),
            id="tier1-yes-tier2-yes-collision",
        ),
        pytest.param(
            _RegisteredCase(
                input_shape="(text: str, file_path: str)",
                output_shape="tuple[Violation, ...]",
                keywords=("section", "heading", "wave", "format"),
            ),
            _TargetCase(
                input_shape="(text: str, file_path: str)",
                output_shape="tuple[Violation, ...]",
                keywords=("column", "ddd", "table", "header"),
            ),
            _ExpectedOutcome(
                verdict="ambiguous",
                tier1=("OUT-A",),
                tier2_id=None,
            ),
            id="tier1-yes-tier2-no-ambiguous",
        ),
        pytest.param(
            _RegisteredCase(
                input_shape="ModelOne",
                output_shape="tuple[Violation, ...]",
                keywords=("cherry-pick", "row-count"),
            ),
            _TargetCase(
                input_shape="ModelTwo",
                output_shape="str",
                keywords=("cherry-pick", "row-count"),
            ),
            _ExpectedOutcome(
                verdict="ambiguous",
                tier1=(),
                tier2_id="OUT-A",
            ),
            id="tier1-no-tier2-yes-ambiguous",
        ),
        pytest.param(
            _RegisteredCase(
                input_shape="ModelOne",
                output_shape="tuple[Violation, ...]",
                keywords=("alpha", "beta"),
            ),
            _TargetCase(
                input_shape="ModelTwo",
                output_shape="str",
                keywords=("totally", "different"),
            ),
            _ExpectedOutcome(
                verdict="clean",
                tier1=(),
                tier2_id=None,
            ),
            id="tier1-no-tier2-no-clean",
        ),
    ],
)
def test_verdict_matrix(
    registered: _RegisteredCase,
    target: _TargetCase,
    expected: _ExpectedOutcome,
) -> None:
    detector = CollisionDetector()
    snapshot = (
        _outcome(
            "OUT-A",
            registered.input_shape,
            registered.output_shape,
            keywords=registered.keywords,
        ),
    )
    candidate_shape = TargetShape(
        input_shape=target.input_shape,
        output_shape=target.output_shape,
        keywords=target.keywords,
    )

    report = detector.check(target=candidate_shape, snapshot=snapshot)

    assert report.verdict == expected.verdict
    assert report.tier1_matches == expected.tier1
    if expected.tier2_id is None:
        assert report.tier2_matches == ()
    else:
        assert len(report.tier2_matches) == 1
        match_id, match_score = report.tier2_matches[0]
        assert match_id == expected.tier2_id
        assert match_score >= 0.4
