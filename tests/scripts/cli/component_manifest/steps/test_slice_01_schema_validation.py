"""Step definitions -- slice-01: schema + validation CLI (walking skeleton).

F-DESIGN-COMPONENT-MANIFEST slice-01. Layer 3 (subprocess / FS acceptance):
the validate_component_manifest CLI is the driving port; the real filesystem
(tmp_path) is the only driven port. Example-based sad paths (Mandate 11).

Step bodies delegate to ``ComponentManifestComposition`` -- a typed lookup plus
a composition call, no inline logic (Mandate-12 criterion 3). The When-step
asserts the manifest file is unchanged by validation (validation is a pure
read) via ``assert_state_delta`` over a port-exposed universe (Mandate 8).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .composition import ComponentManifestComposition
from .domain_types import (
    EXIT_CODE_BY_VERDICT,
    MALFORMED_SHAPE_BY_PHRASE,
    FeatureId,
    ManifestVerdict,
)


scenarios("../slice-01-schema-validation.feature")


@pytest.fixture
def composition(tmp_path: Path) -> ComponentManifestComposition:
    """Production-wired composition root over a tmp_path feature project."""
    return ComponentManifestComposition(feature_root=tmp_path / "feature")


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for the CLI result across When -> Then steps."""
    return {}


# --- Given -------------------------------------------------------------------


@given("a feature whose design directory has been prepared")
def given_design_dir_prepared(composition: ComponentManifestComposition) -> None:
    composition.create_feature_dir(FeatureId("acceptance-fixture-feature"))


@given("the architect has written a well-formed component manifest")
def given_well_formed_manifest(composition: ComponentManifestComposition) -> None:
    composition.write_valid_manifest()


@given("the architect has written a manifest with every section populated")
def given_manifest_every_section(
    composition: ComponentManifestComposition,
) -> None:
    composition.write_manifest_with_every_required_key()


@given(parsers.parse("the architect has written a manifest where {defect}"))
def given_malformed_manifest(
    composition: ComponentManifestComposition, defect: str
) -> None:
    composition.write_malformed_manifest(MALFORMED_SHAPE_BY_PHRASE[defect])


# --- When --------------------------------------------------------------------


@when("the architect validates the component manifest")
def when_validate(
    composition: ComponentManifestComposition, result_box: dict[str, object]
) -> None:
    before = composition.capture_universe()
    result_box["result"] = composition.run_validate_cli()
    after = composition.capture_universe()
    assert_state_delta(
        before=before,
        after=after,
        universe={"manifest.present", "feature_delta.present"},
        expected={
            "manifest.present": unchanged(),
            "feature_delta.present": unchanged(),
        },
    )


# --- Then --------------------------------------------------------------------


@then("the component manifest is accepted")
def then_accepted(result_box: dict[str, object]) -> None:
    result = result_box["result"]
    assert result.exit_code == EXIT_CODE_BY_VERDICT[ManifestVerdict.VALID], (
        f"expected exit 0 (accepted); got {result.exit_code}: {result.stderr}"
    )


@then("the component manifest is refused as malformed")
def then_refused_malformed(result_box: dict[str, object]) -> None:
    result = result_box["result"]
    # A deliberate refusal, not a crash: a scaffold AssertionError also exits
    # non-zero, so the exit code alone is Fixture-Theater-prone. Require a
    # clean refusal -- no Python traceback on stderr.
    assert "Traceback (most recent call last)" not in result.stderr, (
        "the validator crashed rather than refusing the manifest "
        f"(exit {result.exit_code}); stderr:\n{result.stderr}"
    )
    assert result.exit_code == EXIT_CODE_BY_VERDICT[ManifestVerdict.MALFORMED], (
        f"expected exit 2 (malformed); got {result.exit_code}: {result.stderr}"
    )
