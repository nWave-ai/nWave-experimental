"""pytest-bdd binding for f-design-wave-migration slice-03 scenarios.

Driving surface (Mandate-13 prose-surface case): the REAL shipped nw-distill skill
read from disk via the composition root. Step bodies delegate to the composition
root; no business logic in the step bindings (Mandate-12 criterion 3).

GREEN-not-active-RED: the pattern block already ships, so these pass — the expected
state for a format conversion of passing behaviour.
"""

from __future__ import annotations

import pytest
from pytest_bdd import scenarios, then, when

from .composition_slice_03_reusable_pattern import ReusablePatternComposition


scenarios("../slice-03-reusable-pattern.feature")


@pytest.fixture
def pattern() -> ReusablePatternComposition:
    return ReusablePatternComposition()


# --- When ------------------------------------------------------------------


@when("the shipped nw-distill skill is read")
def when_distill_read(pattern: ReusablePatternComposition) -> None:
    pattern.when_the_shipped_distill_skill_is_read()


# --- Then ------------------------------------------------------------------


@then("nw-distill carries the named advisory-skip-gate pattern anchor block")
def then_anchor_exists(pattern: ReusablePatternComposition) -> None:
    pattern.then_pattern_block_is_a_citable_anchor()


@then("the pattern block carries the five Tier-A closed-option slots in its own body")
def then_five_slots(pattern: ReusablePatternComposition) -> None:
    pattern.then_pattern_block_carries_five_tier_a_slots()


@then(
    "the pattern is authored once and referenced by both the DESIGN-absent and "
    "total-AT triggers"
)
def then_single_locus(pattern: ReusablePatternComposition) -> None:
    pattern.then_pattern_is_single_locus_referenced_by_both_rows()
