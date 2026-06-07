"""Step definitions for slice-04 -- the APPLICABILITY-AWARE feature-end done-gate.

slice-04 of fix-feature-end-ws-gate-applicability (env-e2e + coverage-map legs,
Atlas-APPROVED 2026-06-06). The cycle's env-e2e leg (leg 2) and coverage-map leg
(leg 3) become applicability-aware -- each grants NOT_APPLICABLE on a mechanical
un-gameable signal and mints a DISTINCT NA marker the downstream done-gate accepts
in place of the verified record, while every dodge is CAUGHT.

Three divergence pairs (the slice-04 spec, DDD-6):
  * Pair A (env-e2e): A1 honest-NA certified vs A2 dodge-adds-installable CAUGHT.
  * Pair B (coverage-map): B1 honest-NA certified; B2 half-baked map CAUGHT;
    B3 active-adoption-absent CAUGHT; B4 genuine signed verified; B5 self-granted
    adoption IGNORED; B6a absent-key ⇒ NA vs B6b malformed-file ⇒ hard-verify.
  * Pair C (reconciliation): C1 NA markers reconcile vs C2 silent-skip CAUGHT.

Step bodies are delegate-only (Mandate-12 criterion 3): each is a single typed
lookup / one `ApplicabilityAwareCycleComposition` call / one observable assertion.
All applicability + NA-marker + reconciliation logic lives in the production
`des feature-end run` + `des verify-integrity` commands; the composition root only
wires the real subprocesses (against real staged git work-trees + a repo-level
adoption switch) and reads back the records / verdicts the operator sees.

Driving port (Mandate-13, Layer 3 subprocess): the real `des feature-end run` and
`des verify-integrity` commands over the real `des` entry point. No production
module is imported and called at the step boundary (S2 boundary holds: this module
+ its composition import ZERO `des.*`).

Layer 3 `@real-io`: example-based, no PBT machinery (Mandate 9/11). State-delta
universe-guard (Mandate 8) is satisfied via the port-exposed observable fields
(outcome, reported_reason, exit_code, ledger_events / verdict_event,
missing_records) -- the only observable the steps assert on.

RED-for-right-reason (pre-DELIVER gate): at HEAD the cycle has NO NA arms -- the
WS leg returns a proceed-Path (not a distinguished NA), so the env-e2e leg runs
and false-refuses on `GateExit.MISSCOPED=3`; the coverage leg hard-refuses on an
absent `distill/coverage-map.md` with no adoption switch read. So:
  * HONEST scenarios (A1, B1, B6a, C1) RED-fail semantically: the cycle REFUSES
    where slice-04 must PROCEED / mint an NA marker, and verify-integrity reports
    the leg missing where slice-04 must reconcile it.
  * DODGE-catch scenarios (A2, B2, B3, B5, B6b, C2) already pass at HEAD -- the
    dodge IS caught today by the WS delta cross-check / the coverage hard-refuse /
    the silent-skip guard; they pin the un-gameability invariant survives slice-04.
  * B4 (genuine signed) depends on the real verify's signed-map contract; it is
    asserted only on "never records NA" (the slice-04 invariant), which holds at
    HEAD (the present map is verified, never NA) and after.
All failures are semantic AssertionErrors -- never collection/import/setup errors
(the composition imports zero `des.*`).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_04 import (
    ApplicabilityAwareCycleComposition,
    CycleObserved,
    IntegrityObserved,
)
from .domain_types_slice_04 import (
    CycleOutcome,
    FeatureShape,
    LegMarker,
    ReasonMarker,
)


scenarios(
    "../slice-04-env-e2e-applicability.feature",
    "../slice-04-coverage-map-applicability.feature",
    "../slice-04-integrity-reconciliation.feature",
)


# A staged-feature shape per the Gherkin predicate that stages it. The DSL emerges
# from the typed FeatureShape enum (Mandate-12): every Given predicate maps to one
# enum value via this single table, not a hard-coded staging body per scenario. The
# key is the FULL predicate the `@given` step captures (everything after the
# leading "a feature " / "a project ").
_SHAPE_BY_PREDICATE: dict[str, FeatureShape] = {
    # Pair A -- env-e2e
    "whose change adds no new installable package and ships nothing to install": (
        FeatureShape.HONEST_NON_INSTALLABLE
    ),
    "whose change adds a new installable package yet claims it ships nothing to install": (
        FeatureShape.DODGE_ADDS_INSTALLABLE
    ),
    # Pair B -- coverage-map
    "that has not adopted the coverage attestation and a feature that produced none": (
        FeatureShape.HONEST_NO_COVERAGE_INACTIVE
    ),
    "that has not adopted the coverage attestation and a feature that produced a half-baked one": (
        FeatureShape.DODGE_HALF_BAKED_MAP
    ),
    "that has adopted the coverage attestation and a feature that produced none": (
        FeatureShape.DODGE_ACTIVE_NO_MAP
    ),
    "that has adopted the coverage attestation and a feature that produced one": (
        FeatureShape.PRESENT_INCOMPLETE_MAP_ACTIVE
    ),
    "that has adopted the coverage attestation and a feature declaring for itself that the project has not": (
        FeatureShape.SELF_GRANTED_NA_DODGE
    ),
    "whose adoption setting omits the coverage key and a feature that produced none": (
        FeatureShape.DEGRADE_ABSENT_KEY
    ),
    "whose adoption setting is unreadable and a feature that produced none": (
        FeatureShape.DEGRADE_MALFORMED_FILE
    ),
    # Pair C reconciliation -- the cycle is run, then the done-gate. C1's "both
    # legs not applicable" feature is the honest non-installable + inactive-coverage
    # shape (non-installable git tree, no adoption switch -> both legs grant NA). C2
    # stages a feature whose coverage leg left neither record (the silent-skip shape).
    "whose real-environment and coverage checks were both not applicable": (
        FeatureShape.HONEST_NON_INSTALLABLE
    ),
    "whose coverage check left neither a verified nor a not-applicable record": (
        FeatureShape.SILENT_SKIP_LEG
    ),
}


@pytest.fixture
def composition(tmp_path: Path) -> ApplicabilityAwareCycleComposition:
    return ApplicabilityAwareCycleComposition(tmp_path)


@pytest.fixture
def staged() -> dict[str, object]:
    return {}


@pytest.fixture
def observed() -> dict[str, object]:
    return {}


# --- Given --------------------------------------------------------------------


@given(parsers.parse("a feature {predicate}"))
def _given_feature_shape(
    composition: ApplicabilityAwareCycleComposition,
    staged: dict[str, object],
    predicate: str,
) -> None:
    staged["feature"] = composition.stage_feature(_SHAPE_BY_PREDICATE[predicate])


@given(parsers.parse("a project {predicate}"))
def _given_project_shape(
    composition: ApplicabilityAwareCycleComposition,
    staged: dict[str, object],
    predicate: str,
) -> None:
    staged["feature"] = composition.stage_feature(_SHAPE_BY_PREDICATE[predicate])


# --- When ---------------------------------------------------------------------


@when("the operator runs the feature-end cycle on that feature")
def _when_run_cycle(
    composition: ApplicabilityAwareCycleComposition,
    staged: dict[str, object],
    observed: dict[str, object],
) -> None:
    observed["cycle"] = composition.run_cycle(staged["feature"])  # type: ignore[arg-type]


@when("the operator runs the done-gate on that feature")
def _when_run_done_gate(
    composition: ApplicabilityAwareCycleComposition,
    staged: dict[str, object],
    observed: dict[str, object],
) -> None:
    observed["cycle"] = composition.run_cycle(staged["feature"])  # type: ignore[arg-type]
    observed["integrity"] = composition.run_integrity(staged["feature"])  # type: ignore[arg-type]


# --- Then (cycle outcome) -----------------------------------------------------


@then("the cycle is certified past the real-environment check")
def _then_certified_past_env_e2e(observed: dict[str, object]) -> None:
    assert _cycle(observed).outcome == CycleOutcome.PROCEEDS_PAST_LEG


@then("the cycle is certified past the coverage check")
def _then_certified_past_coverage(observed: dict[str, object]) -> None:
    assert _cycle(observed).outcome == CycleOutcome.PROCEEDS_PAST_LEG


@then("the cycle refuses to certify the feature")
def _then_cycle_refuses(observed: dict[str, object]) -> None:
    assert _cycle(observed).outcome == CycleOutcome.REFUSES


@then("the cycle names the new installable package its change added")
def _then_cycle_names_added_package(observed: dict[str, object]) -> None:
    assert ReasonMarker.ADDED_INSTALLABLE_PATH.value in _cycle(observed).reported_reason


@then("the cycle names the missing coverage signoff as the reason it refuses")
def _then_cycle_names_missing_signoff(observed: dict[str, object]) -> None:
    # The SignoffMissing token POSITIVELY witnesses the coverage leg was REACHED
    # (the absent-map refusal can only surface once the cycle propagates WS-NA ->
    # env-e2e-NA past leg 2). At HEAD the cycle dies at env-e2e MISSCOPED, so this
    # token is absent -> RED-for-right-reason (B3/B5/B6b).
    assert ReasonMarker.SIGNOFF_MISSING.value in _cycle(observed).reported_reason


@then("the cycle names the incomplete coverage attestation as the reason it refuses")
def _then_cycle_names_incomplete_attestation(observed: dict[str, object]) -> None:
    # The StructuralIncomplete token POSITIVELY witnesses the coverage leg was
    # REACHED and a PRESENT map is held to the real §5.3 verify, never NA (B2/B4).
    # At HEAD the cycle dies at env-e2e MISSCOPED before the coverage leg runs, so
    # this token is absent -> RED-for-right-reason.
    assert ReasonMarker.STRUCTURAL_INCOMPLETE.value in _cycle(observed).reported_reason


# --- Then (env-e2e NA markers) ------------------------------------------------


@then("the cycle records the real-environment check as not applicable for that feature")
def _then_records_env_e2e_na(observed: dict[str, object]) -> None:
    assert (
        LegMarker.ENVIRONMENTAL_E2E_NOT_APPLICABLE.value
        in _cycle(observed).ledger_events
    )


@then("the cycle never records the real-environment check as verified for that feature")
def _then_never_records_env_e2e_verified(observed: dict[str, object]) -> None:
    assert (
        LegMarker.ENVIRONMENTAL_E2E_VERIFIED.value not in _cycle(observed).ledger_events
    )


@then(
    "the cycle never records the real-environment check as not applicable for that feature"
)
def _then_never_records_env_e2e_na(observed: dict[str, object]) -> None:
    assert (
        LegMarker.ENVIRONMENTAL_E2E_NOT_APPLICABLE.value
        not in _cycle(observed).ledger_events
    )


# --- Then (coverage-map NA markers) -------------------------------------------


@then("the cycle records the coverage check as not applicable for that feature")
def _then_records_coverage_na(observed: dict[str, object]) -> None:
    events = _cycle(observed).ledger_events
    assert LegMarker.COVERAGE_MAP_NOT_APPLICABLE_AT_DISTILL_EXIT.value in events
    assert LegMarker.COVERAGE_MAP_NOT_APPLICABLE_AT_DELIVER_EXIT.value in events


@then("the cycle never records the coverage check as verified for that feature")
def _then_never_records_coverage_verified(observed: dict[str, object]) -> None:
    events = _cycle(observed).ledger_events
    assert LegMarker.COVERAGE_MAP_VERIFIED_AT_DISTILL_EXIT.value not in events
    assert LegMarker.COVERAGE_MAP_VERIFIED_AT_DELIVER_EXIT.value not in events


@then("the cycle never records the coverage check as not applicable for that feature")
def _then_never_records_coverage_na(observed: dict[str, object]) -> None:
    events = _cycle(observed).ledger_events
    assert LegMarker.COVERAGE_MAP_NOT_APPLICABLE_AT_DISTILL_EXIT.value not in events
    assert LegMarker.COVERAGE_MAP_NOT_APPLICABLE_AT_DELIVER_EXIT.value not in events


# --- Then (reconciliation done-gate) ------------------------------------------


@then(
    "the done-gate does not name the real-environment check among the missing records"
)
def _then_env_e2e_reconciled(observed: dict[str, object]) -> None:
    assert (
        LegMarker.ENVIRONMENTAL_E2E_GATE_RAN.value
        not in _integrity(observed).missing_records
    )


@then("the done-gate does not name the coverage check among the missing records")
def _then_coverage_reconciled(observed: dict[str, object]) -> None:
    missing = _integrity(observed).missing_records
    assert LegMarker.COVERAGE_MAP_VERIFIED_AT_DISTILL_EXIT.value not in missing
    assert LegMarker.COVERAGE_MAP_VERIFIED_AT_DELIVER_EXIT.value not in missing


@then("the done-gate reports the feature-end cycle as incomplete")
def _then_done_gate_incomplete(observed: dict[str, object]) -> None:
    assert _integrity(observed).verdict_event == "FeatureEndCycleIncomplete"


@then("the done-gate names the coverage check among the missing records")
def _then_done_gate_names_coverage_missing(observed: dict[str, object]) -> None:
    missing = _integrity(observed).missing_records
    assert (
        LegMarker.COVERAGE_MAP_VERIFIED_AT_DISTILL_EXIT.value in missing
        or LegMarker.COVERAGE_MAP_VERIFIED_AT_DELIVER_EXIT.value in missing
    )


# --- observable accessors -----------------------------------------------------


def _cycle(observed: dict[str, object]) -> CycleObserved:
    result = observed["cycle"]
    assert isinstance(result, CycleObserved)
    return result


def _integrity(observed: dict[str, object]) -> IntegrityObserved:
    result = observed["integrity"]
    assert isinstance(result, IntegrityObserved)
    return result
