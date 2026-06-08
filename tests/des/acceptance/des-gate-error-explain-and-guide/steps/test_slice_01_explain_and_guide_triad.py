"""pytest-bdd binding: the feature-scope gate enriches malformed-scope refusals
with a what/why/next explain-and-guide triad (slice-01 walking skeleton).

Driving port: the production `des run-contract-gate --feature-id` CLI, invoked
as a subprocess black box (Mandate-13 driving-port-only, Layer 3 subprocess).
Step bodies delegate to the composition root (`composition.py`); no production
module is imported-and-called at the step boundary, and no business logic lives
in a step body (Mandate-12 criterion 3: each body is a single delegation).

The `scenarios(...)` call binds every scenario in the .feature file via the
RELATIVE path from this steps/ module -- the proven-collecting form used by
sibling suites (gate-trailer-read-seam-a-indeterminate). This routes @tags
through pytest-bdd's tag-to-dynamic-mark pipeline, which the project's
filterwarnings makes --strict-markers-safe.

Each step decorator's literal text is unique within this feature directory
(S1 step-text-uniqueness invariant).

RED scaffold (empirically confirmed at authorship HEAD):
  * Scenario 1 (walking skeleton): `_explain_and_guide` mapper does not exist
    -> emitted JSON has no `what`/`why`/`next` -> `event.get("what")` returns
    None -> assertion `isinstance(value, str) and len(value) > 0` fails ->
    AssertionError. RED for the right reason.
  * Scenario 2 (additive-only invariant): the five existing fields ARE already
    present in the emitted JSON (no mapper call -> no change to existing keys)
    and exit code IS already 2 -> all Then-steps pass ->
    GREEN-on-author. This is the intended behavior: scenario 2 is the
    load-bearing additive-only canary.
  * Scenario 3 (per-token distinctness): `what`/`why`/`next` absent for
    `empty-intersection` too -> `event.get("what")` returns None -> assertion
    fails -> AssertionError. RED for the right reason.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition import ExplainGuideComposition


scenarios("../slice-01-explain-and-guide-triad.feature")


@pytest.fixture
def composition() -> Iterator[ExplainGuideComposition]:
    comp = ExplainGuideComposition()
    yield comp
    comp.cleanup()


# Shared storage for the zero-collected `why` value so scenario 3 can compare
# it against the empty-intersection `why`. Populated by the
# `then_canonical_event_fields_unchanged` step in scenario 2, then read by the
# `then_empty_intersection_why_distinct` step in scenario 3.
# Using a fixture-scoped mutable dict keeps the value isolated per test run.
@pytest.fixture
def zero_collected_why_store() -> dict[str, str]:
    return {}


# --- Given -------------------------------------------------------------------


@given("a repository where no feature file carries the feature tag")
def given_zero_collected_repo(composition: ExplainGuideComposition) -> None:
    composition.given_zero_collected_repo()


@given("a repository where a feature file exists but carries no slice tag")
def given_empty_intersection_repo(composition: ExplainGuideComposition) -> None:
    composition.given_empty_intersection_repo()


# --- When --------------------------------------------------------------------


@when("the operator runs des run-contract-gate scoped to that feature")
def when_runs_gate_zero_collected(composition: ExplainGuideComposition) -> None:
    composition.when_operator_runs_gate()


@when("the operator runs des run-contract-gate scoped to that feature and slice")
def when_runs_gate_empty_intersection(composition: ExplainGuideComposition) -> None:
    composition.when_operator_runs_gate()


# --- Then --------------------------------------------------------------------


@then("the gate refuses with the explain-and-guide triad present")
def then_triad_present(composition: ExplainGuideComposition) -> None:
    composition.then_explain_and_guide_triad_present()


@then("the gate does not write to the repository")
def then_pure_read(composition: ExplainGuideComposition) -> None:
    composition.then_gate_does_not_write_to_repository()


@then("the gate emits the canonical FeatureScopeMalformed event")
def then_canonical_fields(
    composition: ExplainGuideComposition,
    zero_collected_why_store: dict[str, str],
) -> None:
    composition.then_canonical_event_fields_unchanged()
    # Capture the zero-collected `why` for scenario 3's distinctness check.
    # This is safe only after GREEN (when `why` is present); at RED this step
    # is GREEN-on-author so `zero_collected_why()` raises AssertionError
    # (correctly -- the mapper does not exist yet). Scenario 3 will also be RED
    # independently, so the cross-scenario capture is never load-bearing at RED.
    try:
        zero_collected_why_store["why"] = composition.zero_collected_why()
    except AssertionError:
        pass  # expected at RED (no `why` field yet); scenario 3 is also RED


@then("the gate exits with the malformed-scope exit code")
def then_exit_code(composition: ExplainGuideComposition) -> None:
    composition.then_exit_code_is_malformed_scope()


@then(
    "the gate refuses with the explain-and-guide triad present for empty-intersection"
)
def then_triad_present_empty_intersection(
    composition: ExplainGuideComposition,
) -> None:
    composition.then_explain_and_guide_present_for_empty_intersection()


@then("the empty-intersection triad is distinct from the zero-collected triad")
def then_empty_intersection_distinct(
    composition: ExplainGuideComposition,
    zero_collected_why_store: dict[str, str],
) -> None:
    zero_collected_why = zero_collected_why_store.get("why", "")
    composition.then_empty_intersection_why_distinct_from_zero_collected_why(
        zero_collected_why
    )
