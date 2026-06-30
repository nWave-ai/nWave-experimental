"""pytest-bdd binding for f-rust-test-runner-adapter slice-01 scenarios.

Driving surface (Mandate-13 driving-port-only, Layer 3 subprocess): the REAL
production ``resolve_tool`` helper imported + invoked in a child interpreter over
a GENUINE controlled filesystem + PATH/HOME env. Step bodies delegate to the
composition root (``composition_slice_01_tool_discovery.py``); no business logic
in step bodies (Mandate-12 criterion 3). The ``<rung>`` token is parsed into the
typed ``DiscoveryRung`` enum, so the resolve-step template ranges over the typed
domain vocabulary (DSL emergence, not decorator proliferation).

Active-RED scaffold (atdd_pure -- NOT @skip): RED until DELIVER ships
``src/des/adapters/driven/runner/tool_discovery.py`` with the 3-rung
``resolve_tool`` scale. At HEAD the module is absent, so the child probe import
raises ModuleNotFoundError THERE (rc != 0, no marker); the observable effect
never happens, so each Then fails with a semantic AssertionError, never a
collection / import error.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_01_tool_discovery import ToolDiscoveryComposition
from .domain_types_resolve_tool import DiscoveryRung


scenarios("../slice-01-tool-discovery.feature")


@pytest.fixture
def discovery() -> ToolDiscoveryComposition:
    return ToolDiscoveryComposition()


# --- Given -----------------------------------------------------------------


@given("the tool is on the search PATH")
def given_tool_on_path(discovery: ToolDiscoveryComposition) -> None:
    discovery.given_tool_on_path()


@given("the tool is absent from PATH but installed in a known location")
def given_tool_off_path_in_known_location(
    discovery: ToolDiscoveryComposition,
) -> None:
    discovery.given_tool_off_path_in_known_location()


@given("the tool is absent from PATH and every known location")
def given_tool_absent_everywhere(discovery: ToolDiscoveryComposition) -> None:
    discovery.given_tool_absent_everywhere()


# --- When ------------------------------------------------------------------


@when("the adapter resolves the tool through the discovery scale")
def when_resolve_tool_is_invoked(discovery: ToolDiscoveryComposition) -> None:
    discovery.when_resolve_tool_is_invoked()


# --- Then ------------------------------------------------------------------


@then(parsers.parse("the tool is used from the {rung} rung"))
def then_tool_is_resolved_via(discovery: ToolDiscoveryComposition, rung: str) -> None:
    discovery.then_tool_is_resolved_via(DiscoveryRung(rung))


@then("the discovery yields an indeterminate result naming the remediation")
def then_indeterminate_names_remediation(
    discovery: ToolDiscoveryComposition,
) -> None:
    discovery.then_indeterminate_names_remediation()
