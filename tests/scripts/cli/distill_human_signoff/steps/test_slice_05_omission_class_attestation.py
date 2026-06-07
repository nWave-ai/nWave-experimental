"""Step definitions -- slice-05: omission-class attestation wiring.

F-DISTILL-HUMAN-SIGNOFF slice-05. The `## Signoff` block carries a
cardinality-agnostic `omission-classes-attested:` list keyed by class-id;
the verify gate reads `nWave/data/omission-classes.json` at verify time and
asserts the signoff covers every class-id present (N classes, not a hard-
coded 6). An empty or unparseable file is `MalformedInput` exit 2 -- the
RC-G1 non-empty floor (§4.1a).

Layer 3 (subprocess / FS acceptance). Example-based sad paths (Mandate 11);
the Scenario Outline (G8 cardinality-agnostic surface + RC-G1 non-empty
floor) enumerates closed finite shapes.

Step bodies delegate to `HumanSignoffComposition` -- typed lookup + one
composition call, no inline logic (Mandate-12 criterion 3). The substitute
omission-classes.json lives under the per-test tmp_path so the real
`nWave/data/omission-classes.json` is never mutated by tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition import HumanSignoffComposition
from .domain_types import (
    OMISSION_CLASS_SHAPE_BY_PHRASE,
    OMISSION_CLASS_VERDICT_BY_PHRASE,
    FeatureId,
    OmissionClassListShape,
    OmissionClassVerdict,
)


scenarios("../slice-05-omission-class-attestation.feature")


# --- Fixtures --------------------------------------------------------------


@pytest.fixture
def composition(tmp_path: Path) -> HumanSignoffComposition:
    return HumanSignoffComposition(feature_root=tmp_path / "feature")


@pytest.fixture
def result_box() -> dict[str, object]:
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


@given("a coverage map has been authored and signed by a human")
def given_coverage_map_signed(composition: HumanSignoffComposition) -> None:
    # Seed the substitute omission-classes.json with the seven-class shape
    # so the slice-05 Given steps see a non-empty starting point; the AT-
    # specific Given step below overrides this with the AT's own shape.
    composition.write_omission_classes_json(OmissionClassListShape.SEVEN_CLASSES)
    composition.sign_coverage_map()


# --- Given (slice-05) -------------------------------------------------------


@given("the imported omission class list names a class the signoff did not attest")
def given_imported_list_names_class_not_attested(
    composition: HumanSignoffComposition,
) -> None:
    composition.write_signoff_with_omitted_class()


@given("the imported omission class list has its content edited for one class")
def given_imported_list_content_edited(
    composition: HumanSignoffComposition,
) -> None:
    composition.write_omission_classes_json_with_edited_class_content()


@given(parsers.parse("the imported omission class list is {list_shape}"))
def given_imported_list_shape(
    composition: HumanSignoffComposition, list_shape: str
) -> None:
    shape = OMISSION_CLASS_SHAPE_BY_PHRASE[list_shape]
    composition.write_omission_classes_json(shape)


# --- When -------------------------------------------------------------------


@when("the reviewer verifies the coverage map")
def when_reviewer_verifies(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    result_box["result"] = composition.run_verify_with_substitute_omission_classes()


# --- Then -------------------------------------------------------------------


@then("the verify gate refuses for a missing signoff")
def then_verify_refuses_missing_signoff(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    result = result_box["result"]
    assert composition.verify_gate_refuses_with_signoff_missing(result), (
        f"expected SignoffMissing exit 1; got exit {result.exit_code}: {result.stderr}"
    )


@then(
    "the verify gate consults the imported list and produces a verdict consistent with the edited content"
)
def then_verify_consults_edited_list(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    result = result_box["result"]
    assert composition.verify_gate_accepts(result), (
        f"expected exit 0 (the edited content keeps the same class-id set so "
        f"the attestation stays consistent); got exit {result.exit_code}: "
        f"{result.stderr}"
    )


@then("no gate code was changed between the unedited and edited verifications")
def then_no_gate_code_changed() -> None:
    # AT2 architecture contract: the class list is read from data, not
    # hard-coded in CLI code. The test's existence + green status IS the
    # assertion -- the CLI source carries no class-id literals (probed by
    # the static scan below).
    from scripts.cli import verify_coverage_map as _verify_module

    source = Path(_verify_module.__file__).read_text(encoding="utf-8")
    canonical_ids = (
        "environmental-domain-dropped",
        "behavioural-state-or-transition-dropped",
        "process-mode-or-flag-combination-dropped",
    )
    leaked = [class_id for class_id in canonical_ids if class_id in source]
    assert leaked == [], (
        f"verify_coverage_map.py hard-codes class-ids -- the list MUST be "
        f"data-driven (read from omission-classes.json at verify time). "
        f"Leaked: {leaked}"
    )


@then(parsers.parse("the verify gate responds with {verdict}"))
def then_verify_gate_responds_with(
    composition: HumanSignoffComposition,
    result_box: dict[str, object],
    verdict: str,
) -> None:
    result = result_box["result"]
    expected = OMISSION_CLASS_VERDICT_BY_PHRASE[verdict]
    _assert_verify_verdict(composition, result, expected)


# --- Helpers ----------------------------------------------------------------


def _assert_verify_verdict(
    composition: HumanSignoffComposition,
    result: object,
    expected: OmissionClassVerdict,
) -> None:
    """Dispatch the verdict assertion to the matching composition observable."""
    if expected is OmissionClassVerdict.ACCEPTED:
        assert composition.verify_gate_accepts(result), (
            f"expected exit 0 (accepted); got exit {result.exit_code}: {result.stderr}"
        )
        return
    if expected is OmissionClassVerdict.MALFORMED:
        assert composition.verify_gate_refuses_with_malformed_input(result), (
            f"expected MalformedInput exit 2; got exit {result.exit_code}: "
            f"{result.stderr}"
        )
        return
    raise ValueError(f"unmapped verdict: {expected!r}")
