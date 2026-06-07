"""Step bindings for fix-mandate-9-v2-rollout slice-03 acceptance tests.

Mandate-12 criterion 3 — every step body has <=2 statements, the final
statement is `composition.<method>(...)`. NO control flow (`if`/`for`/
`while`/`try`) in step bodies. DSL emerges from typed parameter coercion
via `parsers.parse` + `domain_types` enum / NewType lookups.

Mandate-13 — driving-port-only. Step modules import ONLY the composition
root (via fixture) + `domain_types`. ZERO `from des.<domain|application|
adapters>.<x> import <internal>` direct-domain imports. The composition
in conftest.py is the single driving-port surface; the slice-03 SUTs are
the retro-audit doc body, the carpaccio gate module (BLOCKING-mode
detector symbol), and the project policy doc (Adapter Criticality table).
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from .domain_types import (
    CRITICALITY_BY_PHRASE,
    VERDICT_BY_AUDIT_PHRASE,
    AdapterCriticalityColumn,
    AdapterCtorName,
    AssertedTag,
    AuditTableColumn,
)


# --- Background ------------------------------------------------------------
#
# Same Background step text shape as slice-01 + slice-02; pytest-bdd binds
# per test-module so the binding is redeclared here for the slice-03 entry
# test. Step body is the canonical composition-fixture availability
# assertion (Mandate-13 + Mandate-12 criterion 3 — one statement, no
# control flow). The Gherkin Background is worded for slice-03 readability
# (`...slice-03 composition...`) so the .feature reads as its own story.


@given("the mandate 9 v2 rollout slice-03 composition is available")
def given_slice_03_composition_available(composition) -> None:
    assert composition is not None


# --- AT-1: Retro-audit artifact body row population (slice-03 closure) ---


@given(
    "the retro-audit artifact at the architecture path is loaded for slice-03 closure"
)
def given_load_audit_body(composition) -> None:
    composition.load_retro_audit_body()


@when("the audit body rows are counted by verdict")
def when_count_audit_body_rows(composition) -> None:
    # Counting is observable as the row-count predicate; no further mutation
    # is needed in the When-step body (Mandate-12 criterion 3: <=2 statements).
    composition.count_populated_audit_rows_with_valid_verdict()


@then("the retro-audit carries at least one populated row")
def then_audit_at_least_one_populated_row(composition) -> None:
    assert composition.count_populated_audit_rows_with_valid_verdict() >= 1


@then(
    parsers.parse(
        "the populated row verdict is one of the closed vocabulary "
        '"{first}" "{second}" "{third}"'
    )
)
def then_audit_row_verdict_in_closed_vocabulary(
    composition, first: str, second: str, third: str
) -> None:
    assert composition.first_populated_audit_row_verdict() in {
        VERDICT_BY_AUDIT_PHRASE[first],
        VERDICT_BY_AUDIT_PHRASE[second],
        VERDICT_BY_AUDIT_PHRASE[third],
    }


@then(
    parsers.parse('the retro-audit header still carries the column "{column_literal}"')
)
def then_audit_header_still_carries_column(composition, column_literal: str) -> None:
    # The audit-header surface from slice-01 stays correct (the slice-01
    # column-name SSOT is the same enum; the closure surface in slice-03
    # only populates rows, never touches the header). Composition method
    # `retro_audit_header_carries_column_literal` is a slice-03 convenience
    # wrapper that loads the header on first call + checks the typed column
    # name; keeps the step body at one composition invocation per Mandate-12
    # criterion 3 (no control flow, ≤2 statements).
    assert composition.retro_audit_header_still_carries(
        AuditTableColumn(column_literal)
    )


# --- AT-2: MandateNineTagMismatch detector BLOCKING-mode promotion -------


@given(
    parsers.parse(
        'a scenario tagged "{scenario_tag}" at "{scenario_file}" line {scenario_line:d} '
        "for blocking detector"
    )
)
def given_blocking_scenario_input(
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
        'the composition root constructs only "{first_ctor}" and "{second_ctor}" '
        "for blocking detector"
    )
)
def given_blocking_composition_evidence(
    composition, first_ctor: str, second_ctor: str
) -> None:
    composition.stage_composition_evidence(
        (AdapterCtorName(first_ctor), AdapterCtorName(second_ctor))
    )


@given("the mandate 9 detector blocking mode is on")
def given_blocking_mode_on(composition) -> None:
    composition.enable_blocking_mode()


@when("the carpaccio gate runs the mandate 9 tag-mismatch detector in blocking mode")
def when_run_blocking_detector(composition) -> None:
    composition.run_blocking_detector()


@then(parsers.parse("the detector raises the gate error with exit code {exit_code:d}"))
def then_detector_raises_with_exit_code(composition, exit_code: int) -> None:
    assert composition.last_blocking_exit_code() == exit_code


@then(parsers.parse('the detector gate error payload event is named "{event_name}"'))
def then_blocking_event_name(composition, event_name: str) -> None:
    assert composition.last_blocking_event_name() == event_name


@then(parsers.parse('the detector gate error payload severity is "{severity}"'))
def then_blocking_severity(composition, severity: str) -> None:
    assert composition.last_blocking_severity() == severity


# --- AT-3: Project Adapter Criticality table initialisation --------------


@given("the atdd infrastructure policy document at the architecture path is loaded")
def given_load_atdd_policy(composition) -> None:
    composition.load_atdd_infrastructure_policy()


@when("the adapter criticality rows are counted")
def when_count_criticality_rows(composition) -> None:
    # Counting is observable downstream; no further state mutation needed
    # in the When-step (Mandate-12 criterion 3).
    composition.count_classified_criticality_rows()


@then(
    parsers.parse(
        'the atdd infrastructure policy carries the section heading "{heading}"'
    )
)
def then_atdd_policy_carries_heading(composition, heading: str) -> None:
    assert composition.atdd_policy_carries_section_heading(heading)


@then(
    parsers.parse('the adapter criticality table carries the column "{column_literal}"')
)
def then_criticality_table_carries_column(composition, column_literal: str) -> None:
    assert composition.criticality_table_carries_column(
        AdapterCriticalityColumn(column_literal)
    )


@then("the adapter criticality table carries at least one classified pair")
def then_at_least_one_classified_pair(composition) -> None:
    assert composition.count_classified_criticality_rows() >= 1


@then(
    parsers.parse(
        'one classified pair carries the criticality literal "{level_phrase}"'
    )
)
def then_one_pair_carries_criticality_level(composition, level_phrase: str) -> None:
    assert (
        composition.first_classified_criticality_row_level()
        is CRITICALITY_BY_PHRASE[level_phrase]
    )
