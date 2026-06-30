"""Step definitions for slice-01 -- the MANIFEST-OPTIONAL WS-floor.

feature-end-ws-gate-manifest-optional (ADR-098, ratified 2026-06-24): the
walking-skeleton floor, when NO ``walking-skeleton.json`` manifest is present,
COMPUTES applicability from the feature's git DELTA rather than fail-closing
(usage exit 2). Four cases:

  AC-1 manifest-less + delta adds no installable root   -> NOT_APPLICABLE;
  AC-2 manifest-less + delta ADDS a new installable root -> FAIL (no dodge);
  AC-3 manifest-less + no tracked history               -> LOUD refuse-to-decide;
  AC-4 manifest present (declares NA, justified)         -> NOT_APPLICABLE
       (preservation: the explicit-manifest path is unchanged).

Step bodies are delegate-only (Mandate-12 criterion 3): each is a single typed
lookup / one `ManifestOptionalFloorComposition` call / one observable assertion.
All manifest-loading + delta-detection + applicability logic lives in the
production `des walking-skeleton-gate` command; the composition root only wires
the real subprocess (against a real staged git work-tree) and reads back the floor
verdict the operator sees.

Driving port (Mandate-13, Layer 3 subprocess): the real `des walking-skeleton-gate`
command over the real `des` entry point. No production module is imported and
called at the step boundary (S2 boundary holds).

Layer 3 `@real-io`: example-based, no PBT machinery (Mandate 9/11). State-delta
universe-guard (Mandate 8) is satisfied via the port-exposed FloorVerdictObserved
fields (verdict, reported_verdict_token, reported_reason, exit_code, raw_stdout) --
the only observable the steps assert on.

RED-for-right-reason (pre-DELIVER gate): at HEAD `_load_manifest` raises (usage
exit 2) the moment the manifest is absent, so AC-1/2/3 RED-fail because the
observed verdict is FAIL_CLOSED (exit 2) rather than NOT_APPLICABLE / FAIL /
INDETERMINATE -- a semantic AssertionError. AC-4 (manifest present) is live-green.
The composition imports zero `des.*`, so failures are never collection/import
errors.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_manifest_optional import (
    FloorVerdictObserved,
    ManifestOptionalFloorComposition,
)
from .domain_types_manifest_optional import FeatureShape, FloorVerdict, ReasonMarker


scenarios("../slice-01-ws-gate-manifest-optional.feature")


# A staged-feature shape per the Gherkin predicate that stages it. The DSL emerges
# from the typed FeatureShape enum (Mandate-12): four Given predicates map to four
# enum values via this single table, not four hard-coded staging bodies. The key
# is the FULL predicate the `@given` step captures (everything after "a feature ").
_FEATURE_SHAPE_BY_PREDICATE: dict[str, FeatureShape] = {
    "manifest-less feature whose change adds no new installable root": (
        FeatureShape.MANIFEST_LESS_ADDS_NO_INSTALLABLE_ROOT
    ),
    "manifest-less feature whose change adds a new installable root": (
        FeatureShape.MANIFEST_LESS_ADDS_NEW_INSTALLABLE_ROOT
    ),
    "manifest-less feature that lives outside any tracked change history": (
        FeatureShape.MANIFEST_LESS_NO_TRACKED_HISTORY
    ),
    "feature that ships a manifest declaring it not applicable with a justified "
    "rationale": (FeatureShape.MANIFEST_PRESENT_NOT_APPLICABLE),
}


@pytest.fixture
def composition(tmp_path: Path) -> ManifestOptionalFloorComposition:
    return ManifestOptionalFloorComposition(tmp_path)


@pytest.fixture
def staged() -> dict[str, Path]:
    return {}


@pytest.fixture
def observed() -> dict[str, FloorVerdictObserved]:
    return {}


# --- Given --------------------------------------------------------------------


@given(parsers.parse("a {predicate}"))
def _given_feature_shape(
    composition: ManifestOptionalFloorComposition,
    staged: dict[str, Path],
    predicate: str,
) -> None:
    staged["feature_dir"] = composition.stage_feature(
        _FEATURE_SHAPE_BY_PREDICATE[predicate]
    )


# --- When ---------------------------------------------------------------------


@when("the operator runs the walking-skeleton floor on that feature")
def _when_run_floor(
    composition: ManifestOptionalFloorComposition,
    staged: dict[str, Path],
    observed: dict[str, FloorVerdictObserved],
) -> None:
    observed["result"] = composition.run_floor(staged["feature_dir"])


# --- Then ---------------------------------------------------------------------


@then("the floor certifies the feature as not applicable to the walking skeleton")
def _then_floor_certifies_not_applicable(
    observed: dict[str, FloorVerdictObserved],
) -> None:
    assert observed["result"].verdict == FloorVerdict.NOT_APPLICABLE
    assert (
        ReasonMarker.NOT_APPLICABLE_VERDICT.value
        == observed["result"].reported_verdict_token
    )


@then("the floor refuses to certify the feature")
def _then_floor_refuses_fail(observed: dict[str, FloorVerdictObserved]) -> None:
    assert observed["result"].verdict == FloorVerdict.FAIL


@then("the floor refuses to decide because it cannot determine what the feature added")
def _then_floor_refuses_to_decide(
    observed: dict[str, FloorVerdictObserved],
) -> None:
    assert observed["result"].verdict == FloorVerdict.INDETERMINATE
    assert ReasonMarker.GIT_UNAVAILABLE.value in observed["result"].reported_reason


@then("the floor does not fail-close on the absent manifest")
def _then_floor_does_not_fail_close(
    observed: dict[str, FloorVerdictObserved],
) -> None:
    # The HEAD behaviour the no-manifest branch must REPLACE: a usage fail-close
    # (exit 2) emitting the WalkingSkeletonGateUsageError event. The floor must
    # NOT fail-close on a merely-absent manifest -- it computes from the delta.
    assert observed["result"].verdict != FloorVerdict.FAIL_CLOSED
    assert observed["result"].exit_code != 2
    assert ReasonMarker.USAGE_FAIL_CLOSE.value not in observed["result"].raw_stdout
