"""pytest-bdd binding: remaining three reason tokens each carry a non-empty
token-specific explain-and-guide triad (slice-02 coverage pins, F1 close).

Driving port: the production `des run-contract-gate --feature-id` CLI, invoked
as a subprocess black box (Mandate-13 driving-port-only, Layer 3 subprocess).
Step bodies are single delegations to the slice-02 composition root (Mandate-12
criterion 3: no business logic in step bodies).

The `scenarios(...)` call uses the relative path from this steps/ module.
Each step decorator's literal text is unique within this feature directory
(S1 step-text-uniqueness invariant -- distinct from all slice-01 literals).

GREEN-on-author (all three scenarios):
  The `_EXPLAIN_AND_GUIDE_TABLE` is already shipped (slice-01 DELIVER).
  Each scenario is GREEN at authorship HEAD because the target token's entry
  is present and non-empty. Non-vacuity argument:

  * Scenario 1 (collection-failed): would FAIL if the `collection-failed`
    table entry had an empty `what`, `why`, or `next`, OR if the `why` string
    were identical to the `zero-collected` entry's `why` (distinctness gate).
    A constant-stub mapper would pass the triad-present check for zero-collected
    but fail the cross-token distinctness assertion here.

  * Scenario 2 (arch-scope-zero-collected): would FAIL if the
    `arch-scope-zero-collected` table entry had an empty field, OR if the
    `why` were identical to the `collection-failed` entry's `why`.

  * Scenario 3 (arch-invariant-failed): would FAIL if the `arch-invariant-failed`
    table entry had an empty field, OR if the `why` were identical to the
    `arch-scope-zero-collected` entry's `why`.

  Together the three distinctness assertions form a chain: each token's `why`
  is proved distinct from an adjacent token, making a constant-stub mapper
  fail at least one assertion in the chain even if only two tokens are compared
  per scenario.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from pytest_bdd import given, scenarios, then, when

from .slice_02_composition import Slice02Composition


scenarios("../slice-02-remaining-token-coverage.feature")


@pytest.fixture
def slice02_composition() -> Iterator[Slice02Composition]:
    comp = Slice02Composition()
    yield comp
    comp.cleanup()


# Cross-scenario state stores for distinctness assertions.
# Each fixture is populated by a Then-step of the preceding scenario and read
# by the distinctness Then-step of the current scenario.


# ---------------------------------------------------------------------------
# Scenario 1: collection-failed
# ---------------------------------------------------------------------------


@given("a repository whose feature scope triggers a pytest collection failure")
def given_collection_failed_repo(slice02_composition: Slice02Composition) -> None:
    slice02_composition.given_collection_failed_repo()


@when("the operator runs des run-contract-gate on the collection-failed scope")
def when_runs_gate_collection_failed(slice02_composition: Slice02Composition) -> None:
    slice02_composition.when_operator_runs_gate()


@then("the gate refuses with a collection-failed explain-and-guide triad")
def then_triad_present_collection_failed(
    slice02_composition: Slice02Composition,
) -> None:
    slice02_composition.then_triad_present_for_reason("collection-failed")


@then("the collection-failed triad why is distinct from the zero-collected triad why")
def then_collection_failed_distinct_from_zero_collected(
    slice02_composition: Slice02Composition,
) -> None:
    slice02_composition.then_why_distinct_from_known_zero_collected()


# ---------------------------------------------------------------------------
# Scenario 2: arch-scope-zero-collected
# ---------------------------------------------------------------------------


@given("a repository whose architecture-invariant tier collects zero tests")
def given_arch_scope_zero_collected_repo(
    slice02_composition: Slice02Composition,
) -> None:
    slice02_composition.given_arch_scope_zero_collected_repo()


@when("the operator runs des run-contract-gate on the vacuous arch scope")
def when_runs_gate_arch_scope_zero(slice02_composition: Slice02Composition) -> None:
    slice02_composition.when_operator_runs_gate()


@then("the gate refuses with an arch-scope-zero-collected explain-and-guide triad")
def then_triad_present_arch_scope_zero(
    slice02_composition: Slice02Composition,
) -> None:
    slice02_composition.then_triad_present_for_reason("arch-scope-zero-collected")


@then(
    "the arch-scope-zero-collected triad why is distinct from the collection-failed triad why"
)
def then_arch_scope_zero_distinct_from_collection_failed(
    slice02_composition: Slice02Composition,
) -> None:
    slice02_composition.then_arch_scope_zero_why_distinct_from_collection_failed()


# ---------------------------------------------------------------------------
# Scenario 3: arch-invariant-failed
# ---------------------------------------------------------------------------


@given("a repository whose architecture-invariant tier has a failing test")
def given_arch_invariant_failed_repo(slice02_composition: Slice02Composition) -> None:
    slice02_composition.given_arch_invariant_failed_repo()


@when("the operator runs des run-contract-gate on the failing arch invariant scope")
def when_runs_gate_arch_invariant_failed(
    slice02_composition: Slice02Composition,
) -> None:
    slice02_composition.when_operator_runs_gate()


@then("the gate refuses with an arch-invariant-failed explain-and-guide triad")
def then_triad_present_arch_invariant_failed(
    slice02_composition: Slice02Composition,
) -> None:
    slice02_composition.then_triad_present_for_reason("arch-invariant-failed")


@then(
    "the arch-invariant-failed triad why is distinct from the arch-scope-zero-collected triad why"
)
def then_arch_invariant_failed_distinct_from_arch_scope_zero(
    slice02_composition: Slice02Composition,
) -> None:
    slice02_composition.then_arch_invariant_failed_why_distinct_from_arch_scope_zero()
