"""Step definitions -- slice-05: the DESIGN-exit wiring slice (last).

F-DESIGN-COMPONENT-MANIFEST slice-05. Layer 3 (subprocess / FS acceptance),
wiring slice -- example-based, no PBT universe (Mandate 11).

AT1 drives the real validate CLI as the DESIGN-exit reviewer check would --
an ungrounded manifest blocks the design wave from exiting. AT2/AT3 read the
real framework catalog + reviewer-check protocol (Pillar 3). AT3 is a presence
check on the protocol document (W1 / B2): it asserts the protocol names the
semantic veto item -- it does NOT test the veto judgment (no oracle).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition import ComponentManifestComposition
from .domain_types import FeatureId
from .framework_assets import FrameworkAssetComposition


scenarios("../slice-05-wiring.feature")


@pytest.fixture
def composition(tmp_path: Path) -> ComponentManifestComposition:
    return ComponentManifestComposition(feature_root=tmp_path / "feature")


@pytest.fixture
def assets() -> FrameworkAssetComposition:
    return FrameworkAssetComposition()


@pytest.fixture
def result_box() -> dict[str, object]:
    return {}


# --- Given -------------------------------------------------------------------


@given("a feature whose design directory has been prepared")
def given_design_dir_prepared(composition: ComponentManifestComposition) -> None:
    composition.create_feature_dir(FeatureId("acceptance-fixture-feature"))


@given("the architect has written a manifest naming a symbol absent from its file")
def given_manifest_ungrounded(
    composition: ComponentManifestComposition,
) -> None:
    composition.write_manifest_with_sut(grounded=False)


@given("the design wave's framework assets")
def given_framework_assets(assets: FrameworkAssetComposition) -> None:
    pass


# --- When --------------------------------------------------------------------


@when("the design-exit review checks the component manifest")
def when_design_exit_review(
    composition: ComponentManifestComposition, result_box: dict[str, object]
) -> None:
    """The DESIGN-exit reviewer check runs the production validate CLI."""
    result_box["result"] = composition.run_validate_cli()


# --- Then --------------------------------------------------------------------


@then("the design wave is blocked from exiting")
def then_design_blocked(result_box: dict[str, object]) -> None:
    result = result_box["result"]
    # A deliberate block, not a crash: a scaffold AssertionError also exits
    # non-zero. Require the validator to have run to a clean refusal (the
    # grounding exit code 1) -- no Python traceback on stderr.
    assert "Traceback (most recent call last)" not in result.stderr, (
        "the validator crashed rather than blocking the design wave "
        f"(exit {result.exit_code}); stderr:\n{result.stderr}"
    )
    assert result.exit_code == 1, (
        "the DESIGN-exit review did not block an ungrounded manifest with the "
        f"grounding exit code 1 (got exit {result.exit_code})"
    )


@then("the framework catalog registers the component manifest gate")
def then_catalog_registers_gate(assets: FrameworkAssetComposition) -> None:
    assert assets.catalog_registers_manifest_gate(), (
        "framework-catalog.yaml has no quality_gates entry for the "
        "component-manifest gate"
    )


@then("the catalog exposes a countable not-applicable waiver signal")
def then_catalog_not_applicable_signal(
    assets: FrameworkAssetComposition,
) -> None:
    assert assets.catalog_exposes_not_applicable_signal(), (
        "the catalog gate entry exposes no countable manifest.not_applicable "
        "signal -- residuality V5: the escape-hatch attractor stays invisible"
    )


@then("a reviewer-check protocol document exists")
def then_protocol_exists(assets: FrameworkAssetComposition) -> None:
    assert assets.reviewer_protocol_exists(), (
        "the DESIGN-exit reviewer-check protocol document does not exist"
    )


@then("the protocol names the declaration-correctness check as a reviewer veto")
def then_protocol_names_veto(assets: FrameworkAssetComposition) -> None:
    assert assets.reviewer_protocol_names_semantic_veto_item(), (
        "the reviewer-check protocol does not name the semantic "
        "declaration-correctness check as a reviewer-veto item (W1 / B2)"
    )
