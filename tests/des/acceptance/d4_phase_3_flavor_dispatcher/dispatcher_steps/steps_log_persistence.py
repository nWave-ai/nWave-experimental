"""Step bindings for D4 Phase 3 slice-04 LogPersistencePort + adapters.

Mandate-12 criterion 3 -- every step body has <=2 statements, the final
statement is `composition.<method>(...)`. NO control flow (`if`/`for`/
`while`/`try`) in step bodies. The DSL emerges from typed parameter coercion
via `parsers.parse` + `domain_types` enum lookups + module-scope helpers in
the composition (`_count_events_in_jsonl`, `_emit_with_stderr_capture`).

Mandate-13 (S2 driving-port-only) -- step modules import ONLY the slice-04
composition root from conftest + `domain_types`. ZERO `from des.<domain|
application|adapters>.<x> import <internal>` direct-domain imports. The
public driving-port entry is `LogPersistencePort.emit(event)` Protocol
method (Layer 3 in-process composition; the per-feature + common log
JSONL writes are real filesystem I/O under tmp_path per the Architecture
of Reference for driven-internal ports). Step bodies invoke composition
methods which delegate to the production adapter via the public Protocol;
no adapter internals are reached from step modules.

S1 step-text uniqueness -- every literal `@given/@when/@then` arg in this
module is unique within the `d4_phase_3_flavor_dispatcher` feature scope
(distinct from `steps_dispatcher.py` slice-01, `steps_carpaccio_refactor.py`
slice-02, and `steps_readiness_gate.py` slice-03 literals). Slice-04
vocabulary talks about "the log persistence composition", "the jsonl log
adapter is configured", "the silent log adapter is configured", "a gate
log event named", "the gate emits the event / each event through the log
persistence port", "the per-feature ledger contains", "the common audit
log contains", "the log persistence port does not raise", "a stderr
diagnostic mentions", "the silent adapter captured", and "the first /
second captured event is named". No collision.
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from .domain_types import COUNT_BY_PHRASE, GateEventId


# --- Background ------------------------------------------------------------


@given("the log persistence composition is available")
def given_log_persistence_composition(log_persistence_composition) -> None:
    assert log_persistence_composition is not None


# --- Given: adapter configuration -----------------------------------------


@given(
    parsers.parse(
        'the jsonl log adapter is configured with fanout enabled for feature "{feature_id}"'
    )
)
def given_jsonl_adapter_with_fanout(
    log_persistence_composition, feature_id: str
) -> None:
    log_persistence_composition.configure_jsonl_adapter_with_fanout(feature_id)


@given("the silent log adapter is configured with capture in memory enabled")
def given_silent_adapter_with_capture(log_persistence_composition) -> None:
    log_persistence_composition.configure_silent_adapter_with_capture()


@given("the per-feature ledger destination is not writeable")
def given_per_feature_destination_not_writeable(log_persistence_composition) -> None:
    log_persistence_composition.make_per_feature_destination_unwriteable()


# --- Given: event authoring -----------------------------------------------


@given(
    parsers.parse(
        'a gate log event named "{event_id}" carrying payload "{payload_summary}"'
    )
)
def given_gate_log_event(
    log_persistence_composition, event_id: str, payload_summary: str
) -> None:
    log_persistence_composition.author_event(GateEventId(event_id), payload_summary)


# --- When: driving-port emit ----------------------------------------------


@when("the gate emits the event through the log persistence port")
def when_gate_emits_event(log_persistence_composition) -> None:
    log_persistence_composition.emit_first_authored_event()


@when("the gate emits each event through the log persistence port")
def when_gate_emits_each_event(log_persistence_composition) -> None:
    log_persistence_composition.emit_each_authored_event()


# --- Then: observable fanout + capture + fail-OPEN ------------------------


@then(
    parsers.parse(
        'the per-feature ledger for "{feature_id}" contains exactly one event named "{event_id}"'
    )
)
def then_per_feature_ledger_contains_one_event(
    log_persistence_composition, feature_id: str, event_id: str
) -> None:
    assert (
        log_persistence_composition.per_feature_event_count(
            feature_id, GateEventId(event_id)
        )
        == 1
    )


@then(
    parsers.parse('the common audit log contains exactly one event named "{event_id}"')
)
def then_common_log_contains_one_event(
    log_persistence_composition, event_id: str
) -> None:
    assert (
        log_persistence_composition.common_log_event_count(GateEventId(event_id)) == 1
    )


@then("the log persistence port does not raise")
def then_emit_did_not_raise(log_persistence_composition) -> None:
    assert log_persistence_composition.emit_raised() is False


@then("a stderr diagnostic mentions the failing destination")
def then_stderr_diagnostic_mentions_destination(log_persistence_composition) -> None:
    assert log_persistence_composition.stderr_diagnostic_mentions(".jsonl")


@then(parsers.parse("the silent adapter captured exactly {count_phrase:w} events"))
def then_silent_adapter_captured_count(
    log_persistence_composition, count_phrase: str
) -> None:
    assert (
        log_persistence_composition.silent_adapter_captured_count()
        == COUNT_BY_PHRASE[count_phrase]
    )


@then(parsers.parse('the first captured event is named "{event_id}"'))
def then_first_captured_event_id(log_persistence_composition, event_id: str) -> None:
    assert log_persistence_composition.silent_adapter_captured_event_id(0) == event_id


@then(parsers.parse('the second captured event is named "{event_id}"'))
def then_second_captured_event_id(log_persistence_composition, event_id: str) -> None:
    assert log_persistence_composition.silent_adapter_captured_event_id(1) == event_id
