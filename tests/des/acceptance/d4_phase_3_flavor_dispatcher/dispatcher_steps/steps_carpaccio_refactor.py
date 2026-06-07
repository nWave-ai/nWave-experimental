"""Step bindings for D4 Phase 3 slice-02 carpaccio-refactor walking skeleton.

Mandate-12 criterion 3 — every step body has <=2 statements, the final
statement is `composition.<method>(...)`. NO control flow (`if`/`for`/
`while`/`try`) in step bodies. The DSL emerges from typed parameter coercion
via `parsers.parse` + `domain_types` enum lookups.

Mandate-13 (S2 driving-port-only) — step modules import ONLY the slice-02
composition root from conftest + `domain_types`. ZERO `from des.<domain|
application|adapters>.<x> import <internal>` direct-domain imports. The
public driving-port entry is `evaluate_atdd_pure_dispatch()` exposed via
the `intercept_composition.evaluate(...)` composition method; step bodies
never reach into intercept internals.

S1 step-text uniqueness — every literal `@given/@when/@then` arg in this
module is unique within the `d4_phase_3_flavor_dispatcher` feature scope
(distinct from `steps_dispatcher.py` slice-01 literals — slice-01 talks
about "the flavor dispatcher composition" / "the dispatcher fires...",
slice-02 talks about "the carpaccio intercept composition" / "the intercept
evaluates..."). No collision.
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from .domain_types import InterceptVerdict


# --- Background ------------------------------------------------------------


@given("the carpaccio intercept composition is available")
def given_intercept_composition(intercept_composition) -> None:
    assert intercept_composition is not None


# --- Given: prompt authoring ----------------------------------------------


@given(
    parsers.parse(
        "a dispatch prompt carrying valid atdd_pure markers for feature "
        '"{feature_id}" entering "{slice_id}" in phase "{phase}"'
    )
)
def given_valid_atdd_pure_prompt(
    intercept_composition,
    feature_id: str,
    slice_id: str,
    phase: str,
) -> None:
    intercept_composition.author_valid_atdd_pure_prompt(feature_id, slice_id, phase)


@given(
    "a dispatch prompt carrying the atdd_pure mode marker but missing the slice marker"
)
def given_defective_atdd_pure_prompt(intercept_composition) -> None:
    intercept_composition.author_defective_atdd_pure_prompt_missing_slice()


@given("a dispatch prompt carrying no DES markers at all")
def given_non_atdd_pure_prompt(intercept_composition) -> None:
    intercept_composition.author_non_atdd_pure_prompt()


# --- Given: carpaccio gate programming -------------------------------------


@given("the carpaccio gate is programmed to clear the entering slice")
def given_carpaccio_clears(intercept_composition) -> None:
    intercept_composition.program_carpaccio_gate_to_clear()


# --- When: evaluate --------------------------------------------------------


@when("the intercept evaluates the dispatch")
def when_intercept_evaluates(intercept_composition) -> None:
    intercept_composition.evaluate()


# --- Then: observable InterceptDecision shape -----------------------------
#
# Three explicit per-verdict @then decorators rather than one parameterized
# template — the Gherkin literals "an allow decision" / "a block decision" /
# "a passthrough decision" carry the natural article variation, and three
# decorators keep step bodies trivially `composition.<method>() is <Enum>`
# (Mandate-12 criterion 3) without contorting `parsers.parse` to skip the
# article token. Each literal is unique within slice-02 scope (S1 OK).


@then("the intercept verdict is an allow decision")
def then_verdict_is_allow(intercept_composition) -> None:
    assert intercept_composition.last_verdict() is InterceptVerdict.ALLOW


@then("the intercept verdict is a block decision")
def then_verdict_is_block(intercept_composition) -> None:
    assert intercept_composition.last_verdict() is InterceptVerdict.BLOCK


@then("the intercept verdict is a passthrough decision")
def then_verdict_is_passthrough(intercept_composition) -> None:
    assert intercept_composition.last_verdict() is InterceptVerdict.PASSTHROUGH


@then("the intercept verdict is recognised as atdd_pure")
def then_is_atdd_pure(intercept_composition) -> None:
    assert intercept_composition.last_is_atdd_pure() is True


@then("the intercept verdict is not recognised as atdd_pure")
def then_is_not_atdd_pure(intercept_composition) -> None:
    assert intercept_composition.last_is_atdd_pure() is False


@then(parsers.parse('the block event name is "{event_name}"'))
def then_block_event_name(intercept_composition, event_name: str) -> None:
    assert intercept_composition.last_block_event() == event_name


@then("the block reason mentions the missing slice marker")
def then_block_reason_mentions_slice(intercept_composition) -> None:
    assert intercept_composition.last_block_reason_mentions("slice")
