"""data-tree-completeness — regression AT for DESPlugin._install_des_data.

Scenario SSOT: ``../data-tree-completeness.feature``.

The fix is ALREADY LANDED in this worktree (uncommitted,
scripts/install/plugins/des_plugin.py) — these three scenarios are the
regression evidence: each one would have FAILED before the fix (the method
did not exist; `nWave/data/` was never installed and nothing verified its
arrival) and each one PASSES now. They stay on disk as a permanent guard
against the defect recurring, not as an active-RED scaffold.

Step bodies delegate to :class:`DataTreeInstallationJourney`
(SSOT-via-Types-Services-DSL mandate, criterion 3: <=2 statements, no logic).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenario, then, when

from .composition import DataTreeInstallationJourney
from .domain_types import ORCHESTRATOR_AFFORDANCE_ENTRY, DataEntryName


_FEATURE = "../data-tree-completeness.feature"


# ---------------------------------------------------------------------------
# Scenario wiring
# ---------------------------------------------------------------------------


@scenario(_FEATURE, "A valid data source tree is installed in full")
def test_valid_data_source_tree_is_installed_in_full():
    """Walking skeleton: happy path — full source, full deployment."""


@scenario(_FEATURE, "A missing data source tree is refused, never silently skipped")
def test_missing_data_source_tree_is_refused():
    """Core oracle: an absent source must never be reported as success."""


@scenario(
    _FEATURE,
    "An entry that fails to arrive at the destination is refused, not reported as success",
)
def test_entry_dropped_in_transit_is_refused():
    """Completeness oracle: verifies the FACT, not the weak 'did not raise' signal."""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def journey(tmp_path: Path) -> DataTreeInstallationJourney:
    """One real-filesystem plugin invocation per scenario."""
    return DataTreeInstallationJourney(tmp_path)


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given("an isolated installation target")
def given_isolated_target(journey: DataTreeInstallationJourney) -> None:
    journey.prepare_isolated_target()


@given("a framework source tree carrying the declared data entries")
def given_declared_data_entries(journey: DataTreeInstallationJourney) -> None:
    journey.seed_declared_data_entries()


@given("no data directory exists anywhere in the framework source")
def given_no_data_directory(journey: DataTreeInstallationJourney) -> None:
    journey.ensure_no_data_directory_anywhere()


@given(
    parsers.parse(
        'the copy step silently drops the "{name}" entry on its way to the destination'
    )
)
def given_copy_step_drops_entry(
    journey: DataTreeInstallationJourney, name: str
) -> None:
    journey.drop_entry_during_copy(DataEntryName(name))


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when("the DES plugin installs the framework data tree")
def when_plugin_installs_data_tree(journey: DataTreeInstallationJourney) -> None:
    journey.install_data_tree()


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then("the plugin reports success")
def then_plugin_reports_success(journey: DataTreeInstallationJourney) -> None:
    journey.assert_plugin_reports_success()


@then("every declared data entry exists at the destination")
def then_every_declared_entry_at_destination(
    journey: DataTreeInstallationJourney,
) -> None:
    journey.assert_every_declared_entry_at_destination()


@then(parsers.parse('the destination carries an "{name}" entry'))
def then_destination_carries_entry(
    journey: DataTreeInstallationJourney, name: str
) -> None:
    journey.assert_destination_carries_entry(DataEntryName(name))


@then("the plugin does not report success")
def then_plugin_does_not_report_success(
    journey: DataTreeInstallationJourney,
) -> None:
    journey.assert_plugin_does_not_report_success()


@then("the failure names the source path it tried")
def then_failure_names_source_path(journey: DataTreeInstallationJourney) -> None:
    journey.assert_failure_names_source_path()


@then("the failure explains WHAT, WHY, and HOW")
def then_failure_explains_what_why_how(journey: DataTreeInstallationJourney) -> None:
    journey.assert_failure_explains_what_why_how()


@then(parsers.parse('the failure names "{name}" as missing'))
def then_failure_names_missing_entry(
    journey: DataTreeInstallationJourney, name: str
) -> None:
    journey.assert_failure_names_missing_entry(DataEntryName(name))


# Re-export for downstream readers / ruff F401 quiet:
_TYPE_REEXPORTS = (ORCHESTRATOR_AFFORDANCE_ENTRY,)
