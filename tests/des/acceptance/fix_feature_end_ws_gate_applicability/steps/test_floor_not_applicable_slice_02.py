"""Step definitions for slice-02 -- the WS-floor NOT_APPLICABLE applicability path.

slice-02 of fix-feature-end-ws-gate-applicability (the un-gameable divergence
pair + the usage guard).

Step bodies are delegate-only (Mandate-12 criterion 3): each is a single typed
lookup / one `WalkingSkeletonFloorComposition` call / one observable assertion.
All applicability + installability-detection logic lives in the production
`des walking-skeleton-gate` command; the composition root only wires the real
subprocess and reads back the floor verdict the operator sees.

Driving port (Mandate-13, Layer 3 subprocess): the real `des walking-skeleton-gate`
command over the real `des` entry point. No production module is imported and
called at the step boundary (S2 boundary holds).

Layer 3 `@real-io`: example-based, no PBT machinery (Mandate 9/11). State-delta
universe-guard (Mandate 8) is satisfied via the port-exposed FloorVerdictObserved
fields (verdict, reported_verdict_token, reported_reason, exit_code) -- the only
observable the steps assert on.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_02 import FloorVerdictObserved, WalkingSkeletonFloorComposition
from .domain_types_slice_02 import FeatureShape, FloorVerdict, ReasonMarker


scenarios("../slice-02-not-applicable-applicability.feature")


# A staged-feature shape per the Gherkin phrase that stages it. The DSL emerges
# from the typed FeatureShape enum (Mandate-12). slice-03 retired the two
# installability divergence-pair phrases (subsumed by the delta-aware
# slice-03-delta-aware-installability.feature); the residual justification-guard
# phrase below is orthogonal and preserved.
_FEATURE_SHAPE_BY_PHRASE: dict[str, FeatureShape] = {
    "claims it ships no walking skeleton but gives no reason": (
        FeatureShape.DECLARED_NOT_APPLICABLE_NO_RATIONALE
    ),
}


@pytest.fixture
def composition(tmp_path: Path) -> WalkingSkeletonFloorComposition:
    return WalkingSkeletonFloorComposition(tmp_path)


@pytest.fixture
def staged() -> dict[str, Path]:
    return {}


@pytest.fixture
def observed() -> dict[str, FloorVerdictObserved]:
    return {}


# --- Given --------------------------------------------------------------------


@given(parsers.parse("a feature that {phrase}"))
def _given_feature_shape(
    composition: WalkingSkeletonFloorComposition,
    staged: dict[str, Path],
    phrase: str,
) -> None:
    staged["feature_dir"] = composition.stage_feature(_FEATURE_SHAPE_BY_PHRASE[phrase])


# --- When ---------------------------------------------------------------------


@when("the operator runs the walking-skeleton floor on that feature")
def _when_run_floor(
    composition: WalkingSkeletonFloorComposition,
    staged: dict[str, Path],
    observed: dict[str, FloorVerdictObserved],
) -> None:
    observed["result"] = composition.run_floor(staged["feature_dir"])


# --- Then ---------------------------------------------------------------------


@then("the floor refuses the claim as unjustified")
def _then_floor_refuses_usage(observed: dict[str, FloorVerdictObserved]) -> None:
    assert observed["result"].verdict == FloorVerdict.USAGE_ERROR


@then("the floor names the missing justification")
def _then_floor_names_missing_rationale(
    observed: dict[str, FloorVerdictObserved],
) -> None:
    assert (
        ReasonMarker.UNJUSTIFIED_RATIONALE.value in observed["result"].reported_reason
    )
