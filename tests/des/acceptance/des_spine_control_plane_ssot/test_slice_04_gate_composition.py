"""pytest-bdd binding for des-spine-control-plane-ssot slice-04.

Thin binding: registers the slice-04 scenarios, imports the step vocabulary from
`steps.steps_slice_04_gate_composition`, and provides the
`gate_composition_fixture` composition-root service. No step definitions or
business logic live here — the SSOT for step bodies is the imported step module +
the `GateCompositionFixture` composition; the SSOT for the scenarios is the
`.feature` file (code is the SSOT, per the DISTILL mandate).

Slice-04 = the gate-composition SSOT (Class C, @infrastructure): the spine sources
its per-lifecycle gate composition from ONE place — the flavor YAML — so the
`subagent.stop` boundary's required-records profile is YAML-driven, not the
hardcoded `_REQUIRED_FEATURE_END_RECORDS` frozenset + the if-ladder
(`subagent_stop_handler.py:1356`). DESIGN facet-1 (DDD-1), `gates_fired_at(E) ==
yaml_composition(flavor, E)`. The `state` per-scenario scratchpad fixture is
reused from the slice-01 conftest (Mandate-12 step-reuse).
"""

from __future__ import annotations

import pytest
from pytest_bdd import scenarios

from .steps.composition_slice_04 import GateCompositionFixture
from .steps.steps_slice_04_gate_composition import *  # noqa: F403  -- vocab


@pytest.fixture
def gate_composition_fixture(tmp_path) -> GateCompositionFixture:
    """The single composition-root service all slice-04 step methods delegate to."""
    return GateCompositionFixture(tmp_path)


scenarios("slice-04-gate-composition.feature")
