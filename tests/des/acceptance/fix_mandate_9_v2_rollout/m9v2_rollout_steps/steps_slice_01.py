"""Step bindings for fix-mandate-9-v2-rollout slice-01 acceptance tests.

Mandate-12 criterion 3 — every step body has <=2 statements, the final
statement is `composition.<method>(...)`. NO control flow (`if`/`for`/
`while`/`try`) in step bodies. DSL emerges from typed parameter coercion
via `parsers.parse` + `domain_types` enum / NewType lookups.

Mandate-13 — driving-port-only. Step modules import ONLY the composition
root (via fixture) + `domain_types`. ZERO `from des.<domain|application|
adapters>.<x> import <internal>` direct-domain imports.
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from .domain_types import (
    SEVERITY_BY_PHRASE,
    VERDICT_BY_PHRASE,
    AdapterCtorName,
    AssertedTag,
    AuditTableColumn,
    SliceKindId,
)


# --- Background ------------------------------------------------------------


@given("the mandate 9 v2 rollout composition is available")
def given_composition_available(composition) -> None:
    assert composition is not None


# --- AT-1: slice_kinds catalog reader -------------------------------------


@given("the carpaccio gate loads the slice_kinds vocabulary from the framework catalog")
def given_load_slice_kinds(composition) -> None:
    composition.load_slice_kinds_from_framework_catalog()


@then(parsers.parse('the slice kind "{kind_id}" is registered'))
def then_slice_kind_registered(composition, kind_id: str) -> None:
    assert composition.slice_kind_is_registered(SliceKindId(kind_id))


# --- AT-2: MandateNineTagMismatch detector --------------------------------


@given(
    parsers.parse(
        'a scenario tagged "{scenario_tag}" at "{scenario_file}" line {scenario_line:d}'
    )
)
def given_scenario_tag_and_location(
    composition,
    scenario_tag: str,
    scenario_file: str,
    scenario_line: int,
) -> None:
    composition.stage_detector_input(
        AssertedTag(scenario_tag), scenario_file, scenario_line
    )


@given(
    parsers.parse(
        'the composition root constructs only "{first_ctor}" and "{second_ctor}"'
    )
)
def given_composition_constructs(
    composition, first_ctor: str, second_ctor: str
) -> None:
    composition.stage_composition_evidence(
        (AdapterCtorName(first_ctor), AdapterCtorName(second_ctor))
    )


@when("the carpaccio gate runs the mandate 9 tag-mismatch detector")
def when_run_detector(composition) -> None:
    composition.run_staged_detector()


@then(parsers.parse('the detector verdict is "{verdict_phrase}"'))
def then_detector_verdict(composition, verdict_phrase: str) -> None:
    assert composition.last_detector_verdict() is VERDICT_BY_PHRASE[verdict_phrase]


@then(parsers.parse('the emitted event is named "{event_name}"'))
def then_emitted_event_name(composition, event_name: str) -> None:
    assert composition.last_detector_event_name() == event_name


@then(parsers.parse('the emitted severity is "{severity_phrase}"'))
def then_emitted_severity(composition, severity_phrase: str) -> None:
    assert (
        composition.last_detector_severity_phrase()
        == SEVERITY_BY_PHRASE[severity_phrase].value
    )


@then(parsers.parse('the stderr capture mentions "{token}"'))
def then_stderr_mentions(composition, token: str) -> None:
    assert composition.last_detector_stderr_mentions(token)


# --- AT-3: retro-audit artifact scaffold ----------------------------------


@given("the retro-audit artifact at the architecture path is loaded")
def given_load_audit(composition) -> None:
    composition.load_retro_audit_header()


@then(parsers.parse('the retro-audit header carries the column "{column_literal}"'))
def then_audit_column_present(composition, column_literal: str) -> None:
    assert composition.retro_audit_carries_column(AuditTableColumn(column_literal))
