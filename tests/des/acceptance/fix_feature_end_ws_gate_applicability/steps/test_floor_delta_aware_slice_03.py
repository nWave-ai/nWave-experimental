"""Step definitions for slice-03 -- the DELTA-AWARE WS-floor installability path.

slice-03 of fix-feature-end-ws-gate-applicability (Ale-ratified B-port, 2026-06-05):
the WS-floor installability cross-check keys on the feature's git DELTA, not the
ambient tree. The three-case divergence:

  (a) the feature's delta ADDS a new installable package + declares not-applicable
      -> the lie is caught mechanically from the delta (FAIL, exit 1);
  (b) the feature's delta adds NO new installable package (a monorepo-internal
      hook-only change, like THIS feature) + same declaration -> honest
      NOT_APPLICABLE (exit 0); the cycle proceeds;
  (c) the feature has no tracked change history -> the delta is undecidable; the
      floor degrades LOUD to INDETERMINATE (exit 4), never a silent NA/FAIL.

Step bodies are delegate-only (Mandate-12 criterion 3): each is a single typed
lookup / one `DeltaAwareFloorComposition` call / one observable assertion. All
delta-detection + installability logic lives in the production
`des walking-skeleton-gate` command; the composition root only wires the real
subprocess (against a real staged git work-tree) and reads back the floor verdict
the operator sees.

Driving port (Mandate-13, Layer 3 subprocess): the real `des walking-skeleton-gate`
command over the real `des` entry point. No production module is imported and
called at the step boundary (S2 boundary holds).

Layer 3 `@real-io`: example-based, no PBT machinery (Mandate 9/11). State-delta
universe-guard (Mandate 8) is satisfied via the port-exposed FloorVerdictObserved
fields (verdict, reported_verdict_token, reported_reason, exit_code) -- the only
observable the steps assert on.

RED-for-right-reason (pre-DELIVER gate): at HEAD the gate keys installability on
the ambient `_detect_installable(feature_root)` probe and has no
`--delta-base-ref` flag and no `INDETERMINATE` verdict, so:
  - case (b) RED-fails because the ambient repo-root `pyproject.toml` reads as
    installable -> the honest monorepo-internal feature is FAILed, not NA;
  - case (c) RED-fails because there is no INDETERMINATE producer (exit 4);
  - case (a) may pass incidentally today (the ambient root is installable), but
    its diagnostic does not name the DELTA-added path.
All failures are semantic AssertionErrors -- never collection/import/setup errors
(the composition imports zero `des.*`).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_03 import DeltaAwareFloorComposition, FloorVerdictObserved
from .domain_types_slice_03 import DeltaShape, FloorVerdict, ReasonMarker


scenarios("../slice-03-delta-aware-installability.feature")


# A staged-feature delta shape per the Gherkin predicate that stages it. The DSL
# emerges from the typed DeltaShape enum (Mandate-12): three Given predicates map
# to three enum values via this single table, not three hard-coded staging bodies.
# The key is the FULL predicate the `@given` step captures (everything after
# "a feature "), so the two surface forms ("whose ..." / "that ...") resolve here
# without any string surgery.
_DELTA_SHAPE_BY_PREDICATE: dict[str, DeltaShape] = {
    "whose change adds no new installable package and justifies that it ships no walking skeleton": (
        DeltaShape.DELTA_ADDS_NO_INSTALLABLE_ROOT
    ),
    "whose change adds a new installable package yet claims it ships no walking skeleton": (
        DeltaShape.DELTA_ADDS_NEW_INSTALLABLE_ROOT
    ),
    "that lives outside any tracked change history yet claims it ships no walking skeleton": (
        DeltaShape.NOT_A_GIT_WORK_TREE
    ),
}


@pytest.fixture
def composition(tmp_path: Path) -> DeltaAwareFloorComposition:
    return DeltaAwareFloorComposition(tmp_path)


@pytest.fixture
def staged() -> dict[str, Path]:
    return {}


@pytest.fixture
def observed() -> dict[str, FloorVerdictObserved]:
    return {}


# --- Given --------------------------------------------------------------------


@given(parsers.parse("a feature {predicate}"))
def _given_feature_delta_shape(
    composition: DeltaAwareFloorComposition,
    staged: dict[str, Path],
    predicate: str,
) -> None:
    staged["feature_dir"] = composition.stage_feature(
        _DELTA_SHAPE_BY_PREDICATE[predicate]
    )


# --- When ---------------------------------------------------------------------


@when("the operator runs the walking-skeleton floor on that feature")
def _when_run_floor(
    composition: DeltaAwareFloorComposition,
    staged: dict[str, Path],
    observed: dict[str, FloorVerdictObserved],
) -> None:
    observed["result"] = composition.run_floor(staged["feature_dir"])


# --- Then ---------------------------------------------------------------------


@then("the floor certifies the feature as not applicable to the walking skeleton")
def _then_floor_certifies_not_applicable(
    observed: dict[str, FloorVerdictObserved],
) -> None:
    assert (
        ReasonMarker.NOT_APPLICABLE_VERDICT.value
        == observed["result"].reported_verdict_token
    )


@then("the floor lets the feature-end proceed past the walking-skeleton floor")
def _then_floor_proceeds(observed: dict[str, FloorVerdictObserved]) -> None:
    assert observed["result"].verdict == FloorVerdict.NOT_APPLICABLE


@then("the floor refuses to certify the feature")
def _then_floor_refuses_fail(observed: dict[str, FloorVerdictObserved]) -> None:
    assert observed["result"].verdict == FloorVerdict.FAIL


@then("the floor names the new installable package its change added")
def _then_floor_names_added_package(
    observed: dict[str, FloorVerdictObserved],
) -> None:
    assert (
        ReasonMarker.ADDED_INSTALLABLE_PATH.value in observed["result"].reported_reason
    )


@then("the floor refuses to decide because it cannot determine what the feature added")
def _then_floor_refuses_to_decide(
    observed: dict[str, FloorVerdictObserved],
) -> None:
    assert observed["result"].verdict == FloorVerdict.INDETERMINATE


@then("the floor names the missing change history as the reason it cannot decide")
def _then_floor_names_missing_history(
    observed: dict[str, FloorVerdictObserved],
) -> None:
    assert ReasonMarker.GIT_UNAVAILABLE.value in observed["result"].reported_reason
