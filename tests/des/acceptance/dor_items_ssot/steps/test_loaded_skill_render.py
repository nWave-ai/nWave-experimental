"""Step definitions + scenario binder for dor-items-ssot slice-02.

Tier A (Gojko-style, production composition root, example-only -- Mandate 10):
the reviewer reads the REAL shipped DoR-validation skill the enforcement path
loads (``nWave/skills/nw-dor-validation/SKILL.md``) and the coherence leg drives
the REAL ``scripts/cli/read_dor_items.py`` standalone reader as a subprocess
(Layer 3 subprocess, Mandate-13 driving-port-only).

Pillar 1: domain language only -- "reviewer", "loaded Definition-of-Ready
validation skill", "readiness item", "authoritative place", "hard gate". No
skill-file / markdown / regex / subprocess jargon in the Gherkin or step names;
the cross-artifact mechanics live in the composition root only.

Pillar 2 (chained narrative): scenarios 2 and 3's ``Given the reviewer has read
the loaded Definition-of-Ready validation skill`` reuses scenario 1's
``When the reviewer reads ...`` step-method (same composition call), not a
copy-pasted fixture.

Mandate-12 (no business logic in steps): every step body delegates to the
``LoadedSkillComposition`` service or asserts on the typed observable it returns
-- no control flow, no inline logic.

S1 step-text uniqueness: every ``@given/@when/@then`` literal here is distinct
from slice-01's ``test_canonical_set.py`` literals (slice-01 says "the canonical
readiness item-set"; slice-02 says "the loaded Definition-of-Ready validation
skill") -- no cross-file shadow in the same feature directory.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_02 import LoadedSkillComposition
from .domain_types_slice_02 import (
    CANONICAL_READINESS_ITEM_COUNT,
    OUTCOME_KPIS_ITEM,
    LoadedSkillView,
)


if TYPE_CHECKING:
    from .domain_types import CanonicalReadinessSet


scenarios("../slice-02-loaded-skill-render.feature")


@pytest.fixture
def skill_composition() -> LoadedSkillComposition:
    return LoadedSkillComposition()


@given("the Definition-of-Ready validation skill a reviewer loads")
def given_loaded_skill_exists(skill_composition: LoadedSkillComposition) -> None:
    # Precondition only: the loaded skill IS the real repo-tracked shipped file
    # the composition points at (no per-test seeding -- the skill is real).
    skill_composition.skill_bytes()


@when(
    "the reviewer reads the loaded Definition-of-Ready validation skill",
    target_fixture="loaded_skill",
)
def when_reviewer_reads_loaded_skill(
    skill_composition: LoadedSkillComposition,
) -> LoadedSkillView:
    return skill_composition.read_loaded_skill()


@given(
    "the reviewer has read the loaded Definition-of-Ready validation skill",
    target_fixture="loaded_skill",
)
def given_reviewer_has_read_loaded_skill(
    skill_composition: LoadedSkillComposition,
) -> LoadedSkillView:
    # Pillar 2: reuse scenario 1's When-action as the chained Given.
    return skill_composition.read_loaded_skill()


@when(
    "the reviewer reads the canonical readiness item-set from the authoritative place",
    target_fixture="ssot_set",
)
def when_reviewer_reads_ssot_set(
    skill_composition: LoadedSkillComposition,
) -> CanonicalReadinessSet:
    return skill_composition.read_ssot_canonical_set()


@then("the loaded skill no longer claims eight readiness items")
def then_skill_no_longer_claims_eight(loaded_skill: LoadedSkillView) -> None:
    assert loaded_skill.claims_stale_count is False


@then("the loaded skill presents all nine canonical readiness items")
def then_skill_presents_all_nine(loaded_skill: LoadedSkillView) -> None:
    # The loaded skill presents the canonical count and claims it explicitly --
    # the "stops claiming 8, presents 9" behavior. Exact item-by-item agreement
    # with the authoritative place is the distinct coherence scenario below.
    assert loaded_skill.enumerated_item_count == CANONICAL_READINESS_ITEM_COUNT
    assert loaded_skill.claims_canonical_count is True


@then("the loaded skill is left unchanged after being read")
def then_loaded_skill_unchanged(
    skill_composition: LoadedSkillComposition,
    loaded_skill: LoadedSkillView,
) -> None:
    # Reading the skill MUST be read-only (unbounded-preservation): a re-read
    # surfaces the identical enumerated items.
    assert (
        skill_composition.read_loaded_skill().enumerated_items
        == loaded_skill.enumerated_items
    )


@then(
    'the loaded skill presents the readiness item "Outcome KPIs defined with '
    "measurable targets and a stated baseline (current-state value the target "
    'is measured against)"'
)
def then_skill_presents_outcome_kpis(loaded_skill: LoadedSkillView) -> None:
    assert loaded_skill.presents_outcome_kpis_item is True
    assert OUTCOME_KPIS_ITEM in loaded_skill.enumerated_items


@then(
    "the loaded skill points at the canonical authoritative place without naming a deprecated data location"
)
def then_skill_points_at_ssot_without_forbidden_literal(
    loaded_skill: LoadedSkillView,
) -> None:
    # The SSOT pointer is present (D-3 render-not-duplicate) AND avoids the
    # forbidden ``nWave/data/`` literal (`validate_no_data_refs.py` forbids it):
    # the pointer cites the bare SSOT filename / the standalone reader instead.
    assert loaded_skill.ssot_pointer_present is True
    assert loaded_skill.ssot_pointer_uses_forbidden_prefix is False


@then(
    "the readiness items the loaded skill presents match the authoritative item-set exactly"
)
def then_skill_items_match_ssot(
    loaded_skill: LoadedSkillView,
    ssot_set: CanonicalReadinessSet,
) -> None:
    # render-not-drift (DESIGN DDD-4): the items the loaded skill presents are
    # exactly the items the authoritative place (SSOT, via the real reader)
    # carries -- the skill is a faithful transcription, not an independent copy.
    assert loaded_skill.enumerated_items == ssot_set.item_names
