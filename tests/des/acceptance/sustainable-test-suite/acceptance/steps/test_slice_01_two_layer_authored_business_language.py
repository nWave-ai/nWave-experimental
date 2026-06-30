"""L1 step definitions — the AUTHORED business-language layer (slice-01).

DESIGN CORRECTION (2026-06-22b, DDD-1C..DDD-5C/8C/10C). These step definitions bind
the L1 business-language scenarios (the WHAT) to the L2 authored driver (the HOW,
`composition.py`). Together they ARE the two-layer authored structure (Gojko/GOOS
canon): every step body is a single delegation to the `driver` facade (Mandate-12
criterion 3: <=2 statements, final = driver.<method>(...), no control flow), and the
literal Gherkin tokens are coerced to typed domain enums (criterion 2: no raw `str`
where an enum exists). There is NO generic engine and NO vocabulary/bindings config.

AUTHORED REUSE (DDD-2C/8C, Finding 1.7/1.9): the declarative step TEXT "Given a
maintainer has authored a feature-delta with a well-formed slice plan" appears in the
walking-skeleton, reuse, refactor-resilience scenarios — binding to ONE step
definition. The SECOND-feature step reuses the SAME authoring vocabulary. Reuse
emerges in the authored steps organized by domain concept, never from configuration.

DRIVING PORT (Mandate-13, Layer 3 subprocess): the SHIPPED `des validate-feature-delta
--require-slice-plan` gate is the SUT, driven subcutaneously by the L2 driver. No
production module is imported and called at the step boundary.

Active-RED (ADR-025/028, atdd_pure): at HEAD the L2 concrete driver's gate-invocation
seam raises AssertionError (MISSING_FUNCTIONALITY) — so every scenario reaching the
gate fails for the right reason, clean collection (not ImportError). DELIVER A_GREEN
authors the driver body; these L1 step definitions stay unchanged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_bdd import given, parsers, scenarios, then, when

from .composition import EXPECTED_VERDICT, expected_accept
from .domain_types import PRODUCTION_SLICE_PLAN_VERDICTS, SlicePlanShape


if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from .composition import GateVerdictObservation, SlicePlanGateDriver


scenarios("../slice-01-two-layer-authored-business-language.feature")


# --- typed-token coercers (Mandate-12 criterion 2) --------------------------

# The shapes the L1 EXAMPLE scenarios name by phrase. The MALFORMED / INFRA_ONLY
# reject shapes are exercised by the @property sweep (which drives the driver across
# the whole `SlicePlanShape` Universe), not by a dedicated example phrase — so the
# slice stays within the carpaccio 5-AT ceiling without losing reject coverage.
_SHAPE_BY_PHRASE = {
    "a well-formed slice plan": SlicePlanShape.WELL_FORMED,
    "no slice plan": SlicePlanShape.NO_PLAN,
}


# --- Given ------------------------------------------------------------------


@given(parsers.parse("a maintainer has authored a feature-delta with {plan_phrase}"))
def given_feature_delta_with_plan(
    driver: SlicePlanGateDriver, tmp_path: Path, plan_phrase: str
) -> None:
    driver.author_feature_delta(tmp_path, _SHAPE_BY_PHRASE[plan_phrase])


@given(
    parsers.parse(
        "a second feature's maintainer has authored a feature-delta with {plan_phrase}"
    )
)
def given_second_feature_delta_with_plan(
    driver: SlicePlanGateDriver, tmp_path: Path, plan_phrase: str
) -> None:
    driver.author_feature_delta(tmp_path, _SHAPE_BY_PHRASE[plan_phrase])


@given("the gate's implementation is exercised through a refactored invocation surface")
def given_refactored_surface(driver: SlicePlanGateDriver) -> None:
    driver.use_refactored_invocation_surface()


# --- When -------------------------------------------------------------------


@when("the maintainer submits the feature-delta to the slice-plan gate")
def when_submit_feature_delta(driver: SlicePlanGateDriver) -> None:
    driver.submit_to_slice_plan_gate()


@when("the maintainer submits both feature-deltas to the slice-plan gate")
def when_submit_both_feature_deltas(driver: SlicePlanGateDriver) -> None:
    driver.submit_to_slice_plan_gate()


# --- Then -------------------------------------------------------------------


@then("the gate accepts the feature-delta")
def then_gate_accepts(driver: SlicePlanGateDriver) -> None:
    assert driver.last_observation().accepted, (
        "the gate must accept this feature-delta — the two-layer authored driver is "
        "not yet wired to the shipped slice-plan gate (MISSING_FUNCTIONALITY)"
    )


@then("the gate rejects the feature-delta")
def then_gate_rejects(driver: SlicePlanGateDriver) -> None:
    assert not driver.last_observation().accepted, (
        "the gate must reject this feature-delta — the two-layer authored driver is "
        "not yet wired to the shipped slice-plan gate (MISSING_FUNCTIONALITY)"
    )


@then(parsers.parse('the gate\'s verdict reads "{verdict_word}" in its own words'))
def then_verdict_reads(driver: SlicePlanGateDriver, verdict_word: str) -> None:
    # `verdict_word` is the gate's PRODUCTION token verbatim from the L1 scenario; the
    # observation is the REAL token parsed from gate output — a token-vs-token compare,
    # not a comparison against a test-side enum copy.
    assert driver.last_observation().verdict == verdict_word, (
        f"the gate must speak the verdict {verdict_word!r} in its own words — the "
        "two-layer authored driver is not yet wired (MISSING_FUNCTIONALITY)"
    )


@then("the gate accepts both feature-deltas")
def then_gate_accepts_both(driver: SlicePlanGateDriver) -> None:
    assert all(obs.accepted for obs in driver.all_observations()), (
        "the gate must accept both features' feature-deltas — the two-layer authored "
        "driver is not yet wired (MISSING_FUNCTIONALITY)"
    )


@then(
    "the same authored business-language steps served both features without re-authoring"
)
def then_steps_reused(driver: SlicePlanGateDriver) -> None:
    assert len(driver.all_observations()) == 2, (
        "the SAME authored business-language steps must serve both features (authored "
        "reuse, DDD-2C) — the two-layer driver is not yet wired (MISSING_FUNCTIONALITY)"
    )


# --- Property (DDD-5C: a property over the finite slice-plan-shape input domain) -----
# The walking-skeleton + example scenarios are layer-3 subprocess (example-based per
# Mandate-9/11); this single quantifiable criterion is a property over the finite
# INPUT-shape domain. NON-TAUTOLOGY (Sentinel fix): the test BUILDS each input shape
# (known by construction) and asserts the REAL gate's OBSERVED verdict equals the gate's
# PRODUCTION constant for that shape (EXPECTED_VERDICT = PRODUCTION_VERDICT_FOR_SHAPE),
# and that the observed verdict ∈ the gate's PRODUCTION verdict Universe
# (PRODUCTION_SLICE_PLAN_VERDICTS). The expectation is the gate's own SSOT, the
# observation is parsed from real output — so a verdict stubbed by test-constant lookup
# cannot pass. Active-RED: each swept shape drives the unimplemented L2 seam and fails
# for the right reason (MISSING_FUNCTIONALITY), not an ImportError.


@given("the maintainer considers every recognised slice-plan shape")
def given_any_recognised_shape(driver: SlicePlanGateDriver) -> None:
    # Property precondition: a recognised shape exists. The per-shape sweep happens in
    # the property's Then steps (each authors + submits across the whole Universe), so
    # this Given is a marker only; the example When binds to the property's When too.
    driver.note_property_scenario()


@then("the gate's verdict for that shape is the one the shape determines")
def then_verdict_matches_shape(driver: SlicePlanGateDriver, tmp_path: Path) -> None:
    _assert_over_shape_universe(
        driver,
        tmp_path,
        lambda obs, shape: obs.verdict == EXPECTED_VERDICT[shape],
        "the gate's REAL verdict for each constructed slice-plan shape must equal the "
        "gate's PRODUCTION verdict for that shape (PRODUCTION_VERDICT_FOR_SHAPE)",
    )


@then("every verdict the gate emits is drawn from its closed verdict vocabulary")
def then_verdict_in_universe(driver: SlicePlanGateDriver, tmp_path: Path) -> None:
    _assert_over_shape_universe(
        driver,
        tmp_path,
        lambda obs, shape: obs.verdict in PRODUCTION_SLICE_PLAN_VERDICTS,
        "every verdict the gate emits must be drawn from its PRODUCTION closed verdict "
        "Universe (PRODUCTION_SLICE_PLAN_VERDICTS, the gate's own SSOT)",
    )


@then("the accept-or-reject decision agrees with the verdict for that shape")
def then_accept_agrees(driver: SlicePlanGateDriver, tmp_path: Path) -> None:
    _assert_over_shape_universe(
        driver,
        tmp_path,
        lambda obs, shape: obs.accepted == expected_accept(shape),
        "the accept-or-reject decision must agree with the verdict for each shape",
    )


def _assert_over_shape_universe(
    driver: SlicePlanGateDriver,
    tmp_path: Path,
    holds: Callable[[GateVerdictObservation, SlicePlanShape], bool],
    failure: str,
) -> None:
    """Sweep the closed `SlicePlanShape` Universe and assert the invariant for ALL.

    The finite-domain PBT expression (the skill's exhaustive sweep for a finite
    Cartesian domain): drive every recognised shape through the authored two-layer
    driver and assert `holds` over each observation. Active-RED: the first shape drives
    the unimplemented L2 seam, raising AssertionError (MISSING_FUNCTIONALITY) — the
    right reason, not an ImportError; DELIVER turns the whole sweep green at once.
    """
    for shape in SlicePlanShape:
        driver.author_feature_delta(tmp_path / shape.value, shape)
        driver.submit_to_slice_plan_gate()
        observation = driver.last_observation()
        assert holds(observation, shape), (
            f"{failure} — failed for a {shape.value!r} slice plan; the two-layer "
            "authored driver is not yet wired (MISSING_FUNCTIONALITY)"
        )
