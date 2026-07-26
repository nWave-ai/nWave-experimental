"""runtime-asset-tier-fail-loud — AT for DESPlugin._install_nwave_runtime_assets.

Scenario SSOT: ``../runtime-asset-tier-fail-loud.feature``.

REORIENTED, not written fresh. These scenarios previously guarded
`_install_des_data`, a method that shipped `nWave/data/` to a SECOND
destination (`<claude_dir>/data/`) that no consumer reads, and that aborted
the DES plugin install on the pipx channel. That method is gone; the contract
it was reaching for -- an install must not silently omit the assets its own
runtime resolves -- now sits on the method that actually ships them.

Each scenario fails without the fail-loud contract: before it, an incomplete
tier and an asset-less external target both produced the same silent
`return None`, so nothing could tell a broken distribution from a valid
minimal target.

Step bodies delegate to :class:`RuntimeAssetShippingJourney`
(SSOT-via-Types-Services-DSL mandate, criterion 3: <=2 statements, no logic).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenario, then, when

from .composition import RuntimeAssetShippingJourney
from .domain_types import DATA_FAMILY, AssetFamilyName, ShippingOutcome


_FEATURE = "../runtime-asset-tier-fail-loud.feature"


# ---------------------------------------------------------------------------
# Scenario wiring
# ---------------------------------------------------------------------------


@scenario(_FEATURE, "A declared nWave tier ships every runtime asset family")
def test_declared_tier_ships_every_family():
    """Walking skeleton: happy path — whole tier, whole deployment."""


@scenario(
    _FEATURE,
    "An entry that fails to arrive at the destination is refused, "
    "not reported as shipped",
)
def test_family_dropped_in_transit_is_refused():
    """Completeness oracle: verifies the FACT, not the weak 'did not raise' signal."""


@scenario(
    _FEATURE,
    "A tier that ships the catalogue but no asset family at all is refused, "
    "naming the channel",
)
def test_empty_declared_tier_is_refused_naming_the_channel():
    """Core oracle: a gap in a real distribution is caught on the builder's side."""


@scenario(_FEATURE, "A tier missing one family still ships the families it does carry")
def test_partial_tier_still_ships():
    """The candidate list is NOT a mandate -- one absent family is not a defect."""


@scenario(
    _FEATURE,
    "An external target carrying no nWave tier is declared not-applicable "
    "and the install continues",
)
def test_external_target_without_tier_is_declared_not_applicable():
    """The other half of the distinction: N/A is NOT a refusal."""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def journey(tmp_path: Path) -> RuntimeAssetShippingJourney:
    """One real-filesystem plugin invocation per scenario."""
    return RuntimeAssetShippingJourney(tmp_path)


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given("an isolated installation target")
def given_isolated_target(journey: RuntimeAssetShippingJourney) -> None:
    journey.prepare_isolated_target()


@given("a framework source tree that declares itself an nWave tier")
def given_declared_nwave_tier(journey: RuntimeAssetShippingJourney) -> None:
    journey.seed_declared_nwave_tier()


@given(
    parsers.parse(
        "a framework source tree that declares itself an nWave tier "
        'without its "{name}" family'
    )
)
def given_declared_tier_missing_family(
    journey: RuntimeAssetShippingJourney, name: str
) -> None:
    journey.seed_declared_nwave_tier(without=AssetFamilyName(name))


@given(
    "a framework source tree that declares itself an nWave tier carrying no asset family"
)
def given_declared_tier_with_no_family(journey: RuntimeAssetShippingJourney) -> None:
    journey.seed_declared_tier_with_no_asset_family()


@given("a framework source tree that carries no nWave tier")
def given_no_nwave_tier(journey: RuntimeAssetShippingJourney) -> None:
    journey.seed_target_without_nwave_tier()


@given(
    parsers.parse(
        'the copy step silently drops the "{name}" family on its way to the destination'
    )
)
def given_copy_step_drops_family(
    journey: RuntimeAssetShippingJourney, name: str
) -> None:
    journey.drop_family_during_copy(AssetFamilyName(name))


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when("the DES plugin ships the nWave runtime assets")
def when_plugin_ships_runtime_assets(journey: RuntimeAssetShippingJourney) -> None:
    journey.ship_runtime_assets()


@when("the DES plugin ships the nWave runtime assets from a prebuilt distribution")
def when_plugin_ships_from_prebuilt(journey: RuntimeAssetShippingJourney) -> None:
    journey.ship_from_prebuilt_distribution()
    journey.ship_runtime_assets()


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then("the assets are reported as shipped")
def then_assets_shipped(journey: RuntimeAssetShippingJourney) -> None:
    journey.assert_outcome(ShippingOutcome.SHIPPED)


@then("the assets are refused")
def then_assets_refused(journey: RuntimeAssetShippingJourney) -> None:
    journey.assert_outcome(ShippingOutcome.REFUSED)


@then("the assets are declared not applicable")
def then_assets_not_applicable(journey: RuntimeAssetShippingJourney) -> None:
    journey.assert_outcome(ShippingOutcome.NOT_APPLICABLE)


@then("every declared asset family exists at the destination")
def then_every_declared_family_at_destination(
    journey: RuntimeAssetShippingJourney,
) -> None:
    journey.assert_every_declared_family_at_destination()


@then(parsers.parse('the destination carries the "{name}" family'))
def then_destination_carries_family(
    journey: RuntimeAssetShippingJourney, name: str
) -> None:
    journey.assert_destination_carries_family(AssetFamilyName(name))


@then(parsers.parse('the refusal names "{name}" as missing'))
def then_refusal_names_family(journey: RuntimeAssetShippingJourney, name: str) -> None:
    journey.assert_refusal_names_family(AssetFamilyName(name))


@then("the refusal explains WHAT, WHY, and HOW")
def then_refusal_explains_what_why_how(journey: RuntimeAssetShippingJourney) -> None:
    journey.assert_refusal_explains_what_why_how()


@then("the refusal names the distribution channel to fix")
def then_refusal_names_the_channel(journey: RuntimeAssetShippingJourney) -> None:
    journey.assert_refusal_names_the_channel()


@then("the install is not refused")
def then_install_not_refused(journey: RuntimeAssetShippingJourney) -> None:
    journey.assert_install_not_refused()


# Re-export for downstream readers / ruff F401 quiet:
_TYPE_REEXPORTS = (DATA_FAMILY,)
