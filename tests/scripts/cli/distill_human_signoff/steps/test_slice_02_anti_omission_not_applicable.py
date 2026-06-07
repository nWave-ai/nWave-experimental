"""Step definitions -- slice-02: anti-omission + not-applicable branch + CAP.

F-DISTILL-HUMAN-SIGNOFF slice-02 (the keystone slice). Layer 3 (subprocess /
FS acceptance): the ``derive_coverage_map`` CLI is the driving port; the real
filesystem (tmp_path) is the only driven port. Example-based sad paths
(Mandate 11) -- the AT3 Scenario Outline enumerates the cap + not-applicable
equivalence classes (closed finite domain; Mandate 9 layer-3, no Hypothesis).

Step bodies delegate to ``HumanSignoffComposition`` -- a typed lookup plus a
composition call, no inline logic (Mandate-12 criterion 3). The When-step
asserts the manifest file is unchanged by rendering (rendering reads inputs,
writes the coverage-map xor refuses) via ``assert_state_delta`` over a
port-exposed universe (Mandate 8).

This slice is RED-for-the-right-reason against the slice-01 production
``derive_coverage_map`` -- the slice-01 CLI does not read the designer's
not-covered attestation, does not enforce the CAP, and does not gate on the
human signoff's ``manifest-not-applicable-attested:`` line. The DELIVER loop
adds those three behaviours; the present scaffold drives that delivery.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.common.state_delta import assert_state_delta, set_to, unchanged

from .composition import HumanSignoffComposition
from .domain_types import (
    CAP_AND_NOT_APPLICABLE_BY_PHRASE,
    EXIT_CODE_BY_VERDICT,
    VERDICT_BY_PHRASE,
    AntiOmissionVerdict,
    CapAndNotApplicableState,
    CoverageDimension,
    CoverageMapVerdict,
    FeatureId,
)


scenarios("../slice-02-anti-omission-not-applicable.feature")


# --- Fixtures --------------------------------------------------------------


@pytest.fixture
def composition(tmp_path: Path) -> HumanSignoffComposition:
    """Production-wired composition root over a tmp_path feature project."""
    return HumanSignoffComposition(feature_root=tmp_path / "feature")


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for the CLI result + scenario-derived state across steps."""
    return {}


# --- Background -------------------------------------------------------------


@given("a feature whose design wave has produced a component manifest")
def given_design_wave_produced_manifest(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    composition.create_feature_dir(FeatureId("acceptance-fixture-feature"))
    result_box["domain_ids"] = (
        composition.write_manifest_with_one_domain_per_dimension()
    )


# --- Given ------------------------------------------------------------------


@given("a manifest domain is left uncovered by every acceptance scenario tag")
def given_one_domain_uncovered(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    # Deliberately leave the BEHAVIOURAL dimension's domain uncovered (the
    # same dimension the slice-01 happy-path AT2 uses, so the per-dimension
    # placement assertion is meaningful).
    result_box["uncovered_dimension"] = CoverageDimension.BEHAVIOURAL
    composition.write_scenario_covering_subset(
        result_box["domain_ids"], leave_uncovered=CoverageDimension.BEHAVIOURAL
    )


@given("the acceptance designer suppresses that domain from the not covered table")
def given_designer_drops_domain(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    composition.author_attestation_dropping_domain(
        domain_ids=result_box["domain_ids"],
        dropped_dimension=result_box["uncovered_dimension"],
    )


@given(
    parsers.parse(
        "the feature is in {state_phrase} with respect to the cap and the not-applicable branch"
    )
)
def given_cap_and_not_applicable_state(
    composition: HumanSignoffComposition,
    result_box: dict[str, object],
    state_phrase: str,
) -> None:
    state: CapAndNotApplicableState = CAP_AND_NOT_APPLICABLE_BY_PHRASE[state_phrase]
    result_box["cap_and_not_applicable_state"] = state
    composition.stage_cap_and_not_applicable_state(state, result_box["domain_ids"])


# --- When -------------------------------------------------------------------


@when("the acceptance designer renders the coverage map")
def when_render(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    before = composition.capture_slice02_universe()
    result_box["result"] = composition.run_derive_coverage_map()
    after = composition.capture_slice02_universe()
    # State-delta universe is port-exposed file-presence names only (Mandate 8).
    # coverage_map.present transitions false -> true ONLY on exit 0; on any
    # refusal (exit 1) the renderer MUST NOT write the map.
    cli_result = result_box["result"]
    if cli_result.exit_code == EXIT_CODE_BY_VERDICT[CoverageMapVerdict.RENDERED]:
        coverage_expected = set_to(True)
    else:
        coverage_expected = unchanged()
    assert_state_delta(
        before=before,
        after=after,
        universe={
            "manifest.present",
            "coverage_map.present",
            "feature_delta.present",
            "attestation.present",
            "signoff.present",
        },
        expected={
            "manifest.present": unchanged(),
            "coverage_map.present": coverage_expected,
            "feature_delta.present": unchanged(),
            "attestation.present": unchanged(),
            "signoff.present": unchanged(),
        },
    )


# --- Then -------------------------------------------------------------------


@then("the renderer refuses for an undeclared omission")
def then_refuses_omission(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    result = result_box["result"]
    token = AntiOmissionVerdict.OMISSION_DETECTED.value
    assert result.exit_code == 1, (
        f"expected exit 1 ({token}); got {result.exit_code}: {result.stderr}"
    )
    assert composition.stderr_contains_refusal_token(token, result), (
        f"refusal token {token!r} missing from stderr\n--\n{result.stderr}"
    )


@then("no coverage map is written to the feature distill directory")
def then_no_coverage_map(composition: HumanSignoffComposition) -> None:
    assert not composition.coverage_map_path().is_file(), (
        "renderer refused but a coverage-map.md was still written -- "
        "the refusal path must NOT emit the artefact"
    )


@then("a coverage map is written to the feature distill directory")
def then_coverage_map_written(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    result = result_box["result"]
    assert result.exit_code == EXIT_CODE_BY_VERDICT[CoverageMapVerdict.RENDERED], (
        f"expected exit 0 (rendered); got {result.exit_code}: {result.stderr}"
    )
    assert composition.coverage_map_path().is_file(), (
        "the renderer reported success but no coverage-map.md was written"
    )


@then(
    "the not covered table places the domain on the dimension row matching its category"
)
def then_uncovered_on_correct_dimension(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    uncovered_dim: CoverageDimension = result_box["uncovered_dimension"]
    uncovered_id = result_box["domain_ids"][uncovered_dim]
    body = composition.read_coverage_map()
    for line in body.splitlines():
        if str(uncovered_id) in line and line.startswith(f"| {uncovered_dim.value}"):
            return
    raise AssertionError(
        f"uncovered domain {uncovered_id!r} not on the row for dimension "
        f"{uncovered_dim.value!r}\n--\n{body}"
    )


@then(parsers.parse("the renderer responds with {verdict_phrase}"))
def then_renderer_responds_with(
    composition: HumanSignoffComposition,
    result_box: dict[str, object],
    verdict_phrase: str,
) -> None:
    verdict = VERDICT_BY_PHRASE[verdict_phrase]
    result = result_box["result"]
    if isinstance(verdict, CoverageMapVerdict):
        # Happy-path: not-applicable + attested -> coverage-map written exit 0.
        assert result.exit_code == EXIT_CODE_BY_VERDICT[verdict], (
            f"expected exit {EXIT_CODE_BY_VERDICT[verdict]} ({verdict.value}); "
            f"got {result.exit_code}: {result.stderr}"
        )
        assert composition.coverage_map_path().is_file(), (
            "the renderer reported success but no coverage-map.md was written"
        )
        return
    # Refusal: AntiOmissionVerdict -- exit 1 + named refusal token on stderr.
    assert result.exit_code == 1, (
        f"expected exit 1 ({verdict.value}); got {result.exit_code}: {result.stderr}"
    )
    assert composition.stderr_contains_refusal_token(verdict.value, result), (
        f"refusal token {verdict.value!r} missing from stderr\n--\n{result.stderr}"
    )
    # Every refusal path MUST NOT emit the coverage-map artefact (fail-closed).
    assert not composition.coverage_map_path().is_file(), (
        f"renderer refused with {verdict.value!r} but a coverage-map.md was "
        f"still written -- the refusal path must NOT emit the artefact"
    )
