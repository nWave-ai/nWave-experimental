"""slice-08 step definitions — CONSOLIDATE-ON-ADD EVAL (DDD-7).

Driving port: the `nw-agent-evals` substrate + the NEW deterministic consolidate-on-add
grader row, driven over real trace-JSONL fixtures (DDD-7 EXTEND, no new framework). The
grader is the SUT; no live agent dispatch, no git, no network. Each step body delegates to
the `ConsolidateOnAddEvalDriver` composition (Mandate-12: ≤2 statements, no inline logic, no
control flow).

Active-RED: the consolidate-on-add grader row does not exist in the substrate yet, so every
scenario's verdict accessor raises a clean AssertionError (MISSING_FUNCTIONALITY) — not an
ImportError at the step boundary, not a malformed-fixture error. DELIVER makes these GREEN by
adding `grade_consolidate_on_add` to the substrate — it does NOT author a new eval framework.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .eval_composition import ConsolidateOnAddEvalDriver
from .eval_domain_types import ConsolidateOnAddEvalVerdict


scenarios("../slice-08-consolidate-on-add-eval.feature")


@pytest.fixture
def eval_driver() -> ConsolidateOnAddEvalDriver:
    return ConsolidateOnAddEvalDriver()


# -- Given ------------------------------------------------------------------


@given("a captured ATD trace that reused the shared vocabulary when adding a slice")
def given_consolidate_on_add(eval_driver: ConsolidateOnAddEvalDriver) -> None:
    eval_driver.given_consolidate_on_add_trace()


@given("a captured ATD trace that only added fresh per-feature steps without reuse")
def given_add_only(eval_driver: ConsolidateOnAddEvalDriver) -> None:
    eval_driver.given_add_only_trace()


@given("a captured ATD trace that cannot be parsed for the reuse signal")
def given_unparseable(eval_driver: ConsolidateOnAddEvalDriver) -> None:
    eval_driver.given_unparseable_trace()


@given("a captured ATD trace path that does not exist on the filesystem")
def given_nonexistent(eval_driver: ConsolidateOnAddEvalDriver) -> None:
    eval_driver.given_nonexistent_trace()


# -- When -------------------------------------------------------------------


@when("the consolidate-on-add grader runs over the trace")
def when_grader_runs(eval_driver: ConsolidateOnAddEvalDriver) -> None:
    eval_driver.when_grader_runs()


# -- Then -------------------------------------------------------------------


@then(parsers.parse('the grader reports the verdict "{verdict}"'))
def then_verdict_is(eval_driver: ConsolidateOnAddEvalDriver, verdict: str) -> None:
    eval_driver.then_verdict_is(ConsolidateOnAddEvalVerdict(verdict))
