"""Step definitions + scenario binder for dor-items-ssot slice-03.

Tier A (Gojko-style, production composition root, example-only -- Mandate 10):
the reviewer reads the REAL shipped DoR-validation skill the enforcement path
loads (``nWave/skills/nw-dor-validation/SKILL.md``) and the coherence leg drives
the REAL ``scripts/cli/read_dor_items.py`` standalone reader as a subprocess
(Layer 3 subprocess, Mandate-13 driving-port-only).

slice-03 closes the SECOND axis: the loaded skill must TELL the reviewer, at the
point of enforcement, that job-traceability is a SEPARATE hard gate ABOVE the
nine readiness items -- NOT readiness item ten (DISCUSS D-5 / DESIGN DDD-3).

Pillar 1: domain language only -- "reviewer", "loaded Definition-of-Ready
validation skill", "readiness item", "separate hard gate", "job-traceability". No
skill-file / markdown / regex / subprocess jargon in the Gherkin or step names;
the cross-artifact mechanics live in the composition root only.

Pillar 2 (chained narrative): scenarios 2 and 3's ``Given the reviewer has read
the loaded Definition-of-Ready validation skill at the point of enforcement``
reuses scenario 1's ``When the reviewer reads ...`` step-method (same composition
call), not a copy-pasted fixture.

Mandate-12 (no business logic in steps): every step body delegates to the
``JobTraceabilityGateComposition`` service or asserts on the typed observable it
returns -- no control flow, no inline logic.

S1 step-text uniqueness: every ``@given/@when/@then`` literal here is distinct
from slice-01 (``test_canonical_set.py``) and slice-02
(``test_loaded_skill_render.py``) literals in the same feature directory --
slice-03 says "at the point of enforcement" / "separate hard gate above the
readiness items", which neither sibling declares. No cross-file shadow.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_03 import JobTraceabilityGateComposition
from .domain_types_slice_03 import (
    SEPARATE_HARD_GATE_TOKEN,
    JobTraceabilityGateView,
)


if TYPE_CHECKING:
    from .domain_types import CanonicalReadinessSet


scenarios("../slice-03-separate-hard-gate.feature")


@pytest.fixture
def gate_composition() -> JobTraceabilityGateComposition:
    return JobTraceabilityGateComposition()


@given("the Definition-of-Ready validation skill a reviewer loads to enforce readiness")
def given_loaded_skill_for_enforcement(
    gate_composition: JobTraceabilityGateComposition,
) -> None:
    # Precondition only: the loaded skill IS the real repo-tracked shipped file
    # the composition points at (no per-test seeding -- the skill is real).
    gate_composition.skill_bytes()


@when(
    "the reviewer reads the loaded Definition-of-Ready validation skill at the point of enforcement",
    target_fixture="gate_stance",
)
def when_reviewer_reads_skill_at_enforcement(
    gate_composition: JobTraceabilityGateComposition,
) -> JobTraceabilityGateView:
    return gate_composition.read_job_traceability_stance()


@given(
    "the reviewer has read the loaded Definition-of-Ready validation skill at the point of enforcement",
    target_fixture="gate_stance",
)
def given_reviewer_has_read_skill_at_enforcement(
    gate_composition: JobTraceabilityGateComposition,
) -> JobTraceabilityGateView:
    # Pillar 2: reuse scenario 1's When-action as the chained Given.
    return gate_composition.read_job_traceability_stance()


@when(
    "the reviewer reads the separate hard gates from the authoritative place",
    target_fixture="ssot_set",
)
def when_reviewer_reads_ssot_hard_gates(
    gate_composition: JobTraceabilityGateComposition,
) -> CanonicalReadinessSet:
    return gate_composition.read_ssot_canonical_set()


@then(
    "the loaded skill tells the reviewer job-traceability is a separate hard gate above the readiness items"
)
def then_skill_tells_separate_gate_above_items(
    gate_stance: JobTraceabilityGateView,
) -> None:
    assert gate_stance.states_job_traceability_is_separate_hard_gate is True
    assert gate_stance.states_separate_gate_is_above_readiness_items is True


@then("the loaded skill does not count job-traceability among the nine readiness items")
def then_skill_does_not_count_gate_among_items(
    gate_stance: JobTraceabilityGateView,
) -> None:
    # Conjunction guard (D-5): the loaded skill PRESENTS job-traceability as a
    # separate hard gate AND keeps it OUT of the enumerated nine. Asserting only
    # the negative would pass vacuously on a skill silent about job-traceability
    # (Fixture Theater -- a behavioral slice's AT must fail RED without GREEN);
    # pairing it with the positive presence makes the scenario RED at baseline and
    # meaningfully guards "do not fold the gate into the nine" at GREEN.
    assert gate_stance.states_job_traceability_is_separate_hard_gate is True
    assert gate_stance.counts_job_traceability_among_readiness_items is False


@then(
    "the separate hard gate the loaded skill presents matches the separate hard gate the authoritative place carries"
)
def then_skill_separate_gate_matches_ssot(
    gate_stance: JobTraceabilityGateView,
    ssot_set: CanonicalReadinessSet,
) -> None:
    # render-not-drift (DESIGN DDD-4): the separate gate the loaded skill names is
    # exactly the separate hard gate the authoritative place (SSOT, via the real
    # reader) carries -- the skill is a faithful transcription of the second axis,
    # not an independent copy.
    assert gate_stance.states_job_traceability_is_separate_hard_gate is True
    assert SEPARATE_HARD_GATE_TOKEN in ssot_set.separate_hard_gates
