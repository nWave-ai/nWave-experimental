"""Step definitions + scenario binder for dor-items-ssot slice-01.

Tier A (Gojko-style, production composition root, example-only -- Mandate 10):
the reviewer reads the canonical Definition-of-Ready set through the real
`des dor-items` subcommand (Layer 3 subprocess, Mandate-13 driving-port-only).

Pillar 1: domain language only -- "reviewer", "canonical readiness item-set",
"readiness item", "hard gate". No CLI / subcommand / YAML / exit-code jargon in
the Gherkin or the step names; the subprocess mechanics live in the composition
root only.

Pillar 2 (chained narrative): the second and third scenarios' `Given the
reviewer has read the canonical readiness item-set` reuses the walking
skeleton's `When the reviewer reads ...` step-method (same composition call),
not a copy-pasted fixture.

Mandate-12 (no business logic in steps): every step body delegates to the
`CanonicalSetReaderComposition` service or asserts on the typed observable it
returns -- no control flow, no inline logic.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition import CanonicalSetReaderComposition
from .domain_types import (
    CANONICAL_READINESS_ITEM_COUNT,
    CANONICAL_READINESS_ITEMS,
    JOB_TRACEABILITY_GATE,
    CanonicalReadinessSet,
)


scenarios("../slice-01-canonical-set.feature")


@pytest.fixture
def composition() -> CanonicalSetReaderComposition:
    return CanonicalSetReaderComposition()


@given(
    "the canonical Definition-of-Ready item-set is published in one authoritative place"
)
def given_canonical_set_published(
    composition: CanonicalSetReaderComposition,
) -> None:
    # Precondition only: the authoritative place IS the repo-tracked SSOT the
    # composition points at (no per-test seeding -- the SSOT is real data).
    composition._ssot_path  # noqa: B018 -- name the precondition surface


@when(
    "the reviewer reads the canonical readiness item-set",
    target_fixture="canonical_set",
)
def when_reviewer_reads_set(
    composition: CanonicalSetReaderComposition,
) -> CanonicalReadinessSet:
    return composition.read_canonical_set()


@given(
    "the reviewer has read the canonical readiness item-set",
    target_fixture="canonical_set",
)
def given_reviewer_has_read_set(
    composition: CanonicalSetReaderComposition,
) -> CanonicalReadinessSet:
    # Pillar 2: reuse the walking skeleton's When-action as the chained Given.
    return composition.read_canonical_set()


@then("the reviewer sees all nine canonical readiness items")
def then_sees_all_nine_items(canonical_set: CanonicalReadinessSet) -> None:
    assert canonical_set.item_names == CANONICAL_READINESS_ITEMS


@then("the authoritative place is left unchanged after being read")
def then_authoritative_place_unchanged(
    composition: CanonicalSetReaderComposition,
    canonical_set: CanonicalReadinessSet,
) -> None:
    # Reading the set MUST be read-only (unbounded-preservation): the SSOT must
    # still be present and surface the same nine items on a second read.
    assert composition.read_canonical_set().item_names == canonical_set.item_names


@then(
    'the reviewer sees the readiness item "Outcome KPIs defined with measurable targets"'
)
def then_sees_outcome_kpis_item(canonical_set: CanonicalReadinessSet) -> None:
    assert "Outcome KPIs defined with measurable targets" in canonical_set.item_names


@then("the reviewer sees job-traceability listed as a separate hard gate")
def then_sees_job_traceability_separate_gate(
    canonical_set: CanonicalReadinessSet,
) -> None:
    assert JOB_TRACEABILITY_GATE in canonical_set.separate_hard_gates


@then(
    "the reviewer does not see job-traceability counted among the nine readiness items"
)
def then_job_traceability_not_a_readiness_item(
    canonical_set: CanonicalReadinessSet,
) -> None:
    assert len(canonical_set.items) == CANONICAL_READINESS_ITEM_COUNT
