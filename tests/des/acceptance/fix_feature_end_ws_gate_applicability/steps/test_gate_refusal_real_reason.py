"""Step definitions for slice-01 -- the feature-end gate's truthful refusal.

slice-01 of fix-feature-end-ws-gate-applicability (the walking-skeleton slice).

Step bodies are delegate-only (Mandate-12 criterion 3): each is a single typed
lookup / one `FeatureEndGateRefusalComposition` call / one observable assertion.
All gate + diagnostic logic lives in the production `des feature-end run`
command; the composition root only wires the real subprocess and reads back the
reported refusal reason the operator sees.

Driving port (Mandate-13, Layer 3 subprocess): the real `des feature-end run`
command over the real `des` entry point. No production module is imported and
called at the step boundary (S2 boundary holds).

Layer 3 `@real-io`: example-based, no PBT machinery (Mandate 9/11). State-delta
universe-guard (Mandate 8) is satisfied via the port-exposed CycleRefusalObserved
fields (outcome, reported_reason, exit_code) -- the only observable the steps
assert on.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition import CycleRefusalObserved, FeatureEndGateRefusalComposition
from .domain_types import CycleOutcome, ReasonMarker, StagedFeature


scenarios("../slice-01-gate-refusal-real-reason.feature")


# A staged-feature shape per the Gherkin phrase that stages it. The DSL emerges
# from the typed StagedFeature enum (Mandate-12): two Given phrases map to two
# enum values via this single table, not two hard-coded staging bodies.
_FEATURE_SHAPE_BY_PHRASE: dict[str, StagedFeature] = {
    "has no manifest to check": StagedFeature.NO_MANIFEST,
    "is missing its feature root": StagedFeature.MANIFEST_NO_ROOT,
}


@pytest.fixture
def composition(tmp_path: Path) -> FeatureEndGateRefusalComposition:
    return FeatureEndGateRefusalComposition(tmp_path)


@pytest.fixture
def staged() -> dict[str, Path]:
    return {}


@pytest.fixture
def observed() -> dict[str, CycleRefusalObserved]:
    return {}


# --- Given --------------------------------------------------------------------


@given("an operator on a developer checkout running the feature-end cycle")
def _given_operator_on_dev_checkout(
    composition: FeatureEndGateRefusalComposition,
) -> None:
    # The developer-checkout precondition is wired by the composition root on
    # construction (the honest `.git/` autoskip marker). No expected output is
    # set here -- only the input state.
    assert isinstance(composition, FeatureEndGateRefusalComposition)


@given(parsers.parse("a feature whose walking-skeleton floor {phrase}"))
def _given_feature_floor_shape(
    composition: FeatureEndGateRefusalComposition,
    staged: dict[str, Path],
    phrase: str,
) -> None:
    staged["feature_dir"] = composition.stage_feature(_FEATURE_SHAPE_BY_PHRASE[phrase])


@given(parsers.parse("a feature whose walking-skeleton manifest {phrase}"))
def _given_feature_manifest_shape(
    composition: FeatureEndGateRefusalComposition,
    staged: dict[str, Path],
    phrase: str,
) -> None:
    staged["feature_dir"] = composition.stage_feature(_FEATURE_SHAPE_BY_PHRASE[phrase])


# --- When ---------------------------------------------------------------------


@when("the operator runs the feature-end cycle on that feature")
def _when_run_cycle(
    composition: FeatureEndGateRefusalComposition,
    staged: dict[str, Path],
    observed: dict[str, CycleRefusalObserved],
) -> None:
    observed["result"] = composition.run_cycle(staged["feature_dir"])


# --- Then ---------------------------------------------------------------------


@then("the feature-end cycle refuses to certify the feature done")
def _then_cycle_refuses(observed: dict[str, CycleRefusalObserved]) -> None:
    assert observed["result"].outcome == CycleOutcome.REFUSED


@then("the reported reason names the missing walking-skeleton manifest")
def _then_reason_names_missing_manifest(
    observed: dict[str, CycleRefusalObserved],
) -> None:
    assert ReasonMarker.MISSING_MANIFEST.value in observed["result"].reported_reason


@then("the reported reason names the missing feature root")
def _then_reason_names_missing_feature_root(
    observed: dict[str, CycleRefusalObserved],
) -> None:
    assert ReasonMarker.MISSING_FEATURE_ROOT.value in observed["result"].reported_reason


@then("the reported reason is not the runtime freshness notice")
def _then_reason_is_not_freshness_notice(
    observed: dict[str, CycleRefusalObserved],
) -> None:
    assert (
        ReasonMarker.RUNTIME_FRESHNESS.value not in observed["result"].reported_reason
    )
