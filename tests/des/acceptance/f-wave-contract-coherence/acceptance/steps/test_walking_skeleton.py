"""pytest-bdd binding for f-wave-contract-coherence slice-01 (walking skeleton).

Driving surface (Mandate-13 driving-port-only): the REAL flavor_dispatcher
registry-resolution read path over the SHIPPED nWave/waves/discuss.yaml registry
file (Layer 3 composition). Step bodies delegate to the composition root
(composition_walking_skeleton.py); no business logic in step bodies (Mandate-12).
The <boundary> parameter parses once into the WaveBoundary enum, so one scenario
shape ranges over the DISCUSS gate-in / gate-out boundaries.

Active-RED scaffold (atdd_pure -- NOT @skip): each scenario is RED until DELIVER
ships nWave/waves/discuss.yaml (gate_stack SSOT-A verbatim from
atdd_pure.yaml:181-190) + the dispatcher's registry-resolution read path. Every
case fails with a semantic AssertionError naming the missing registry / resolution
seam, never a collection / import / setup error.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_walking_skeleton import WaveContractRegistryComposition
from .domain_types import WaveBoundary


scenarios("../walking-skeleton.feature")


@pytest.fixture
def registry() -> WaveContractRegistryComposition:
    return WaveContractRegistryComposition()


# --- Given -----------------------------------------------------------------


@given(
    "the canonical wave-contract registry file for the DISCUSS wave is shipped in the repo"
)
def given_discuss_registry_file_is_shipped(
    registry: WaveContractRegistryComposition,
) -> None:
    registry.given_discuss_registry_file_is_shipped()


# --- When ------------------------------------------------------------------


@when("the maintainer reads the DISCUSS wave-contract from the registry")
def when_maintainer_reads_discuss_wave_contract_from_registry(
    registry: WaveContractRegistryComposition,
) -> None:
    registry.when_maintainer_reads_discuss_wave_contract_from_registry()


@when(
    parsers.parse(
        "the dispatcher resolves the DISCUSS {boundary} stack from the registry "
        "as the default source"
    )
)
def when_dispatcher_resolves_discuss_stack_from_registry(
    registry: WaveContractRegistryComposition, boundary: str
) -> None:
    registry.when_dispatcher_resolves_discuss_stack_from_registry(
        WaveBoundary(boundary)
    )


# --- Then ------------------------------------------------------------------


@then(
    "the DISCUSS wave-contract declares a gate stack with a gate-in and a "
    "gate-out boundary"
)
def then_discuss_contract_declares_gate_stack_with_both_boundaries(
    registry: WaveContractRegistryComposition,
) -> None:
    registry.then_discuss_contract_declares_gate_stack_with_both_boundaries()


@then(
    parsers.parse(
        "the resolved {boundary} stack is sourced from the registry and lists "
        "at least one gate"
    )
)
def then_resolved_stack_is_sourced_from_registry_and_nonempty(
    registry: WaveContractRegistryComposition, boundary: str
) -> None:
    registry.then_resolved_stack_is_sourced_from_registry_and_nonempty(
        WaveBoundary(boundary)
    )


@then(
    parsers.parse(
        "the resolved gate-id sequence equals the DISCUSS {boundary} sequence "
        "in force today"
    )
)
def then_resolved_sequence_equals_sequence_in_force_today(
    registry: WaveContractRegistryComposition, boundary: str
) -> None:
    registry.then_resolved_sequence_equals_sequence_in_force_today(
        WaveBoundary(boundary)
    )
