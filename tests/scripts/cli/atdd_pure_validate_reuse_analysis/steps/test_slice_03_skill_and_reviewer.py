"""Step definitions: the DESIGN skill emits the canonical shape; reviewer vetoes.

F-DESIGN-REUSE-FIRST-GATE slice-03 (PARKED -- moved into the collected tests/
tree by the DELIVER loop when slice-03 is delivered). DDD-8, DDD-4.

Layer 3 (cross-artifact / framework-asset acceptance). Example-only, no PBT
machinery (Mandate 9/11): each check is a single normative-source identity
assertion over a shipped repository asset -- there is no input domain to
generate.

The checks are read-only over the framework assets; the cross-artifact When
steps assert via `assert_state_delta` over a port-exposed bytes universe that
neither asset is mutated by the comparison (Mandate 8).

Step bodies delegate to `FrameworkAssetComposition`; no inline business logic
(Mandate-12 criterion 3).

RED contract (Mandate 7): on master the nw-design skill template spells the
decision `CREATE NEW` (space) and the reviewer carries no reuse-first critique
dimension, so the slice-03 assertions FAIL with a semantic `AssertionError`
(MISSING_FUNCTIONALITY RED) and PASS once the slice-03 crafter EXTENDS the two
assets. Imports resolve cleanly -- `REUSE_ANALYSIS_HEADING` /
`REUSE_ANALYSIS_COLUMNS` are DISTILL scaffolds present in
`validate_feature_delta.py` today.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .framework_assets import (
    FrameworkAssetComposition,
    ReviewerDimensionView,
    SkillTemplateView,
)


scenarios("../slice-03-skill-and-reviewer.feature")


@pytest.fixture
def composition() -> FrameworkAssetComposition:
    """Production composition root over the live repository framework assets."""
    return FrameworkAssetComposition()


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for the asset views + universe across When -> Then steps."""
    return {}


# --- Given -------------------------------------------------------------------


@given("the nw-design skill and the validate-feature-delta module")
def given_skill_and_module(composition: FrameworkAssetComposition) -> None:
    # The assets exist in the repository tree -- nothing to provision.
    assert composition.nw_design_skill.is_file()


@given("the nw-solution-architect-reviewer carries the reuse-first critique dimension")
def given_reviewer(composition: FrameworkAssetComposition) -> None:
    assert composition.reviewer_agent.is_file()


# --- When --------------------------------------------------------------------


@when("the architect compares the skill's Reuse Analysis template to the gate constant")
def when_compare_template(
    composition: FrameworkAssetComposition, result_box: dict[str, object]
) -> None:
    result_box["universe_before"] = composition.capture_universe()
    result_box["template"] = composition.read_skill_template()


@when("the architect inspects the skill's Reuse Analysis decision token")
def when_inspect_token(
    composition: FrameworkAssetComposition, result_box: dict[str, object]
) -> None:
    result_box["universe_before"] = composition.capture_universe()
    result_box["template"] = composition.read_skill_template()


@when(
    "a feature-delta presents an unjustified CREATE_NEW and a silently omitted "
    "overlapping component"
)
def when_present_weak_reuse(
    composition: FrameworkAssetComposition, result_box: dict[str, object]
) -> None:
    result_box["universe_before"] = composition.capture_universe()
    result_box["dimension"] = composition.read_reviewer_dimension()


# --- Then --------------------------------------------------------------------


@then("the skill template heading equals the canonical Reuse Analysis heading")
def then_heading_matches(
    composition: FrameworkAssetComposition, result_box: dict[str, object]
) -> None:
    template = result_box["template"]
    assert isinstance(template, SkillTemplateView)
    assert template.heading == composition.canonical_heading


@then("the skill template columns equal the REUSE_ANALYSIS_COLUMNS constant")
def then_columns_match(
    composition: FrameworkAssetComposition, result_box: dict[str, object]
) -> None:
    template = result_box["template"]
    assert isinstance(template, SkillTemplateView)
    assert template.columns == composition.canonical_columns


@then("the skill template uses the CREATE_NEW token")
def then_uses_create_new(result_box: dict[str, object]) -> None:
    template = result_box["template"]
    assert isinstance(template, SkillTemplateView)
    assert template.uses_create_new_token


@then("the skill template does not produce the legacy CREATE NEW spelling")
def then_no_legacy_spelling(result_box: dict[str, object]) -> None:
    template = result_box["template"]
    assert isinstance(template, SkillTemplateView)
    assert not template.uses_legacy_spelling


@then("the reviewer flags the unjustified CREATE_NEW as a high issue")
def then_flags_unjustified(result_box: dict[str, object]) -> None:
    dimension = result_box["dimension"]
    assert isinstance(dimension, ReviewerDimensionView)
    assert dimension.flags_unjustified_create_new


@then("the reviewer flags the silently omitted overlapping component as a high issue")
def then_flags_omitted_overlap(
    composition: FrameworkAssetComposition, result_box: dict[str, object]
) -> None:
    dimension = result_box["dimension"]
    assert isinstance(dimension, ReviewerDimensionView)
    assert dimension.flags_silently_omitted_overlap
    # bounded-change: the comparison reads the assets, never mutates them.
    assert_state_delta(
        before=result_box["universe_before"],  # type: ignore[arg-type]
        after=composition.capture_universe(),
        universe={"nw_design_skill.bytes", "reviewer_agent.bytes"},
        expected={
            "nw_design_skill.bytes": unchanged(),
            "reviewer_agent.bytes": unchanged(),
        },
    )
