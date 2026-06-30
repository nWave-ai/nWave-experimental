"""pytest-bdd binding for f-design-wave-migration slice-01 scenarios.

Driving surface (Mandate-13 prose-surface case): the REAL shipped nw-distill skill
read from disk via the composition root. Step bodies delegate to the composition
root; no business logic in the step bindings (Mandate-12 criterion 3).

GREEN-not-active-RED: row 7b already ships, so these pass — the expected state for
a format conversion of passing behaviour. Each oracle stays mutation-verifiable.
"""

from __future__ import annotations

import pytest
from pytest_bdd import scenarios, then, when

from .composition_slice_01_design_skip_advisory import (
    DesignSkipAdvisoryComposition,
)


scenarios("../slice-01-design-skip-advisory.feature")


@pytest.fixture
def design_skip() -> DesignSkipAdvisoryComposition:
    return DesignSkipAdvisoryComposition()


# --- When ------------------------------------------------------------------


@when("the shipped nw-distill skill is read")
def when_distill_read(design_skip: DesignSkipAdvisoryComposition) -> None:
    design_skip.when_the_shipped_distill_skill_is_read()


# --- Then ------------------------------------------------------------------


@then("nw-distill keys a DESIGN-absent advisory off the missing Code-Design section")
def then_trigger_exists(design_skip: DesignSkipAdvisoryComposition) -> None:
    design_skip.then_design_absent_trigger_exists()


@then("the advisory proposes the DESIGN wave as the remedy")
def then_proposes_design(design_skip: DesignSkipAdvisoryComposition) -> None:
    design_skip.then_advisory_proposes_nw_design()


@then(
    "the advisory branches on absence versus presence and is silent when DESIGN "
    "is present"
)
def then_branches(design_skip: DesignSkipAdvisoryComposition) -> None:
    design_skip.then_advisory_branches_absent_vs_present_silent()


@then("the advisory proceeds to DISTILL on any answer and never blocks")
def then_never_blocks(design_skip: DesignSkipAdvisoryComposition) -> None:
    design_skip.then_advisory_never_blocks()
