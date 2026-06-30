"""pytest-bdd binding for f-design-wave-migration slice-04 scenarios.

Driving surface (Mandate-13 prose-surface case): the REAL shipped nw-distill +
nw-deliver skills read from disk via the composition root. Step bodies delegate to
the composition root; no business logic in the step bindings (Mandate-12 criterion
3). The Scenario Outline ``<matrix>`` token is parsed into the typed
``DesignMatrix`` enum, so one step template ranges over both matrices (DSL
emergence, not a decorator per matrix).

GREEN-not-active-RED: all four reconciliation loci already ship, so these pass —
the expected state for a format conversion of passing behaviour.
"""

from __future__ import annotations

import pytest
from pytest_bdd import parsers, scenarios, then, when

from .composition_slice_04_design_block_removed import (
    DesignBlockRemovedComposition,
)
from .domain_types_design_wave_migration import DesignMatrix


scenarios("../slice-04-design-block-removed.feature")


@pytest.fixture
def removal() -> DesignBlockRemovedComposition:
    return DesignBlockRemovedComposition()


# --- When ------------------------------------------------------------------


@when("the shipped nw-distill skill is read")
def when_distill_read(removal: DesignBlockRemovedComposition) -> None:
    removal.when_the_shipped_distill_skill_is_read()


@when("the shipped nw-deliver skill is read")
def when_deliver_read(removal: DesignBlockRemovedComposition) -> None:
    removal.when_the_shipped_deliver_skill_is_read()


# --- Then ------------------------------------------------------------------


@then(
    parsers.parse(
        'the "{matrix}" matrix reconciles its DESIGN-absent block to an advisory'
    )
)
def then_matrix_reconciled(removal: DesignBlockRemovedComposition, matrix: str) -> None:
    removal.then_matrix_design_block_reconciled_to_advisory(DesignMatrix[matrix])


@then(
    "the nw-deliver DESIGN read is no longer mandatory and reads the artifact if "
    "present"
)
def then_deliver_read_not_mandatory(
    removal: DesignBlockRemovedComposition,
) -> None:
    removal.then_deliver_design_read_not_mandatory()


@then(
    "the nw-deliver reading-enforcement no longer hard-requires brief.md but "
    "still requires the surviving reads"
)
def then_deliver_enforcement_reconciled(
    removal: DesignBlockRemovedComposition,
) -> None:
    removal.then_deliver_reading_enforcement_brief_not_hard_required()
