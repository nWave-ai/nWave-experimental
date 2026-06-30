"""pytest-bdd binding for the fix-cohort-gate-preauthoring slice-01 scenarios.

Driving surface (Mandate-16 driving-port-only, Layer 3 composition): the REAL
``cohort_classifier._count_ats`` count function (the [REF] Driving Ports seam) via
the composition root over a crafted hermetic feature-delta staged under
``tmp_path``. Step bodies delegate to the composition
(``composition_cohort_preauthoring.py``); no business logic lives in step bodies
(Mandate-15).

active-RED scaffold (atdd_pure -- NOT @skip): AC-1 (placement-only) and AC-3
(both, candidate list larger than authored) are RED at HEAD -- the count function
does not yet count the Test Placement candidate list nor return the larger of the
two. AC-2 (authored preserved) and AC-4 (neither) are live-green preservation
guards. Each failing scenario fails with a semantic ``AssertionError`` naming the
missing seam, never a collection / import / setup error.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_cohort_preauthoring import CohortPreauthoringComposition


scenarios("../slice-01-cohort-preauthoring.feature")


@pytest.fixture
def cohort() -> CohortPreauthoringComposition:
    return CohortPreauthoringComposition()


# --- Given -----------------------------------------------------------------


@given(
    parsers.parse(
        "a feature-delta listing {count:d} candidate acceptance tests in its "
        "Test Placement section"
    )
)
def given_placement_list(cohort: CohortPreauthoringComposition, count: int) -> None:
    cohort.given_placement_candidate_count(count)


@given("a feature-delta with no Test Placement candidate list")
def given_no_placement(cohort: CohortPreauthoringComposition) -> None:
    cohort.given_no_placement_section()


@given(parsers.parse("a feature-delta with {count:d} authored Gherkin scenarios"))
def given_authored_scenarios(cohort: CohortPreauthoringComposition, count: int) -> None:
    cohort.given_authored_scenario_count(count)


@given(parsers.parse("the feature-delta also has {count:d} authored Gherkin scenarios"))
def given_also_authored_scenarios(
    cohort: CohortPreauthoringComposition, count: int
) -> None:
    cohort.given_authored_scenario_count(count)


@given("the feature-delta has no authored Gherkin scenarios")
def given_no_authored(cohort: CohortPreauthoringComposition) -> None:
    cohort.given_no_authored_scenarios()


@given("the feature-delta has no Test Placement candidate list")
def given_and_no_placement(cohort: CohortPreauthoringComposition) -> None:
    cohort.given_no_placement_section()


# --- When ------------------------------------------------------------------


@when("the cohort classifier counts the feature-delta candidate acceptance tests")
def when_classifier_counts(
    cohort: CohortPreauthoringComposition, tmp_path: Path
) -> None:
    cohort.when_classifier_counts_candidates(tmp_path)


# --- Then ------------------------------------------------------------------


@then(parsers.parse("the reported candidate-AT count is {expected:d}"))
def then_reported_count_is(
    cohort: CohortPreauthoringComposition, expected: int
) -> None:
    cohort.then_reported_count_is(expected)
