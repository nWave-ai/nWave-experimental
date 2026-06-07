"""Step bindings for D4 Phase 3 slice-01 flavor-dispatcher walking skeleton.

Mandate-12 criterion 3 — every step body has ≤2 statements, the final
statement is `composition.<method>(...)`. NO control flow (`if`/`for`/
`while`/`try`) in step bodies. The DSL emerges from typed parameter coercion
via `parsers.parse` + `domain_types` enum lookups.

Mandate-13 — driving-port-only. Step modules import ONLY the composition
root from conftest + `domain_types`. ZERO `from des.<domain|application|
adapters>.<x> import <internal>` direct-domain imports.
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from .domain_types import (
    COUNT_BY_PHRASE,
    ON_FAILURE_BY_PHRASE,
    OUTCOME_BY_PHRASE,
    FlavorId,
    GateId,
    LifecycleEventName,
)


# --- Background ------------------------------------------------------------


@given("the flavor dispatcher composition is available")
def given_composition(composition) -> None:
    assert composition is not None


# --- Given: flavor authoring -----------------------------------------------


@given(
    parsers.parse(
        'a flavor named "{flavor_id}" with one gate "{gate_id}" '
        'on event "{event}" with on_failure "{on_failure_phrase}"'
    )
)
def given_single_gate_flavor(
    composition,
    flavor_id: str,
    gate_id: str,
    event: str,
    on_failure_phrase: str,
) -> None:
    composition.author_flavor(
        FlavorId(flavor_id),
        LifecycleEventName(event),
        [(GateId(gate_id), ON_FAILURE_BY_PHRASE[on_failure_phrase])],
    )


@given(
    parsers.parse('a flavor named "{flavor_id}" with three gates on event "{event}":')
)
def given_three_gate_flavor(
    composition,
    flavor_id: str,
    event: str,
    datatable,
) -> None:
    # datatable rows skip header row; each row = [gate_id, on_failure_phrase]
    gates = [(GateId(row[0]), ON_FAILURE_BY_PHRASE[row[1]]) for row in datatable[1:]]
    composition.author_flavor(FlavorId(flavor_id), LifecycleEventName(event), gates)


# --- Given: gate invoker programming ---------------------------------------


@given(
    parsers.parse(
        'the gate invoker records "{gate_id}" as a {outcome_phrase} invocation'
    )
)
def given_gate_outcome(composition, gate_id: str, outcome_phrase: str) -> None:
    composition.record_gate_outcome(GateId(gate_id), OUTCOME_BY_PHRASE[outcome_phrase])


# --- When: dispatch --------------------------------------------------------


@when(
    parsers.parse(
        'the dispatcher fires the lifecycle event "{event}" for flavor "{flavor_id}"'
    )
)
def when_dispatch(composition, event: str, flavor_id: str) -> None:
    composition.dispatch(LifecycleEventName(event), FlavorId(flavor_id))


# --- Then: observable outcomes --------------------------------------------


# DRY: one binding matches all three tense/number Gherkin variants
# ("completes with … gate result" | "completed with … gate results" |
# "recorded … gate results"). The phrasings stay load-bearing prose in the
# .feature files; the binding captures count_phrase via alternation (TD-12).
@then(
    parsers.re(
        r"the composition (?:completes with|completed with|recorded) "
        r"(?P<count_phrase>\w+) gate results?"
    )
)
def then_records_n_results(composition, count_phrase: str) -> None:
    assert len(composition.last_result.gate_results) == COUNT_BY_PHRASE[count_phrase]


@then(parsers.parse('the recorded gate is "{gate_id}"'))
def then_recorded_gate(composition, gate_id: str) -> None:
    assert composition.last_result.gate_results[0].gate_id == gate_id


@then("the composition did not halt")
def then_did_not_halt(composition) -> None:
    assert composition.last_result.halted is False


@then(parsers.parse('the composition halted at the blocking gate "{gate_id}"'))
def then_halted_at(composition, gate_id: str) -> None:
    assert composition.last_result.halted is True
    assert composition.last_result.blocking_gate_id == gate_id


@then(parsers.parse('the gate "{gate_id}" carries a warning annotation'))
def then_warning_annotation(composition, gate_id: str) -> None:
    result = next(
        r for r in composition.last_result.gate_results if r.gate_id == gate_id
    )
    assert result.warning_annotation is not None
