"""Step definitions -- slice-02: declared-at provenance + sut: grounding.

F-DESIGN-COMPONENT-MANIFEST slice-02. Layer 3 (subprocess / FS acceptance):
the validate_component_manifest CLI is the driving port. Example-based sad
paths (Mandate 11) -- one example per failure mode.

Shares ``ComponentManifestComposition`` (Pillar 3, shared vocabulary). Step
bodies delegate; the When-step's universe-bound assertion (Mandate 8) lives in
the shared When-step imported below.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .composition import ComponentManifestComposition
from .domain_types import EXIT_CODE_BY_VERDICT, FeatureId, ManifestVerdict


scenarios("../slice-02-provenance-grounding.feature")


@pytest.fixture
def composition(tmp_path: Path) -> ComponentManifestComposition:
    return ComponentManifestComposition(feature_root=tmp_path / "feature")


@pytest.fixture
def result_box() -> dict[str, object]:
    return {}


# --- Given -------------------------------------------------------------------


@given("a feature whose design directory has been prepared")
def given_design_dir_prepared(composition: ComponentManifestComposition) -> None:
    composition.create_feature_dir(FeatureId("acceptance-fixture-feature"))


@given("the architect has written a manifest naming only real symbols")
def given_manifest_grounded(composition: ComponentManifestComposition) -> None:
    composition.write_manifest_with_sut(grounded=True)


@given("the architect has written a manifest naming a symbol absent from its file")
def given_manifest_ungrounded(
    composition: ComponentManifestComposition,
) -> None:
    composition.write_manifest_with_sut(grounded=False)


@given("the architect has written a manifest stamped by the distill wave")
def given_manifest_wrong_wave(
    composition: ComponentManifestComposition,
) -> None:
    composition.write_manifest_declared_at_distill()


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


@then("the component manifest is refused as stale")
def then_refused_stale(result_box: dict[str, object]) -> None:
    result = result_box["result"]
    # A deliberate refusal, not a crash: a scaffold AssertionError also exits
    # non-zero, so the exit code alone is Fixture-Theater-prone. Require the
    # CLI to have run to a clean refusal -- no Python traceback on stderr.
    assert "Traceback (most recent call last)" not in result.stderr, (
        "the validator crashed rather than refusing the manifest "
        f"(exit {result.exit_code}); stderr:\n{result.stderr}"
    )
    assert result.exit_code == EXIT_CODE_BY_VERDICT[ManifestVerdict.STALE], (
        f"expected exit 1 (stale); got {result.exit_code}: {result.stderr}"
    )


@then("the component manifest is refused as malformed")
def then_refused_malformed(result_box: dict[str, object]) -> None:
    result = result_box["result"]
    assert "Traceback (most recent call last)" not in result.stderr, (
        "the validator crashed rather than refusing the manifest "
        f"(exit {result.exit_code}); stderr:\n{result.stderr}"
    )
    assert result.exit_code == EXIT_CODE_BY_VERDICT[ManifestVerdict.MALFORMED], (
        f"expected exit 2 (malformed); got {result.exit_code}: {result.stderr}"
    )
