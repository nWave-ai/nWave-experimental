"""Shared step vocabulary for the fix-atdd-pure-common-audit-log-ssot suite.

Mandate-12 (SSOT via Types + Services + DSL): the suite's `.feature` files
share ONE step vocabulary across slices (slice-01 and slice-02 today). Each
decorator below is a parameterized template over a typed-enum parameter
(from ``domain_types.py``) -- the DSL emerges from the typed domain
concepts, not from one decorator per literal phrase.

Mandate-12 criterion 3: every step body is <=2 statements, ends in a single
``composition.<service>(...)`` call (or a typed-lookup + call), and contains
no control flow. Business logic lives in ``composition.py`` service methods,
never here.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, then, when

from .composition import CommonAuditLogSsotComposition
from .domain_types import (
    ARCH_CALLER_SCENARIO_BY_PHRASE,
    ARCH_VERDICT_BY_PHRASE,
    CALLER_ID_BY_PATH,
    EVENT_KIND_BY_PHRASE,
    READER_METHOD_BY_PHRASE,
    FeatureId,
    SliceId,
)


@pytest.fixture
def composition() -> CommonAuditLogSsotComposition:
    """The production composition root, fresh per scenario."""
    return CommonAuditLogSsotComposition()


# --- slice-02b: reader-feature-filter step vocabulary ------------------------
# Three decorators bind slice-02b-reader-feature-filter.feature. The
# parameterized templates dispatch through `READER_METHOD_BY_PHRASE` so the
# parametrize matrix over three readers reuses one binding per Given/When/Then.


@given(
    parsers.parse(
        "the common audit log holds a complete feature-end cycle for"
        ' feature "{feature_id}"'
    )
)
def given_complete_cycle(
    composition: CommonAuditLogSsotComposition, feature_id: str
) -> None:
    composition.given_complete_feature_end_cycle_for(FeatureId(feature_id))


@when(
    parsers.parse(
        "the aggregate reader {reader_method} is invoked with feature filter"
        ' "{feature_id}"'
    )
)
def when_reader_with_filter(
    composition: CommonAuditLogSsotComposition,
    reader_method: str,
    feature_id: str,
) -> None:
    composition.when_aggregate_reader_invoked_with_filter(
        READER_METHOD_BY_PHRASE[reader_method],
        FeatureId(feature_id),
    )


@when(
    parsers.parse(
        "the aggregate reader {reader_method} is invoked without a feature filter"
    )
)
def when_reader_without_filter(
    composition: CommonAuditLogSsotComposition, reader_method: str
) -> None:
    composition.when_aggregate_reader_invoked_without_filter(
        READER_METHOD_BY_PHRASE[reader_method],
    )


@then(parsers.parse("the reader returns the alpha-only subset for {reader_method}"))
def then_reader_alpha_subset(
    composition: CommonAuditLogSsotComposition, reader_method: str
) -> None:
    composition.then_reader_returned_alpha_subset(
        READER_METHOD_BY_PHRASE[reader_method],
    )


@then("the reader does not return any beta records")
def then_reader_no_beta(composition: CommonAuditLogSsotComposition) -> None:
    composition.then_reader_returned_no_beta_records()


@then(
    parsers.parse("the reader returns the cross-feature aggregate for {reader_method}")
)
def then_reader_cross_feature(
    composition: CommonAuditLogSsotComposition, reader_method: str
) -> None:
    composition.then_reader_returned_cross_feature_aggregate(
        READER_METHOD_BY_PHRASE[reader_method],
    )


@then("the CLI exits non-zero against the target feature")
def then_cli_exits_non_zero_for_target(
    composition: CommonAuditLogSsotComposition,
) -> None:
    composition.then_cli_exits_non_zero_for_target()


@then(parsers.parse('the CLI verdict names the target feature "{feature_id}"'))
def then_cli_names_target(
    composition: CommonAuditLogSsotComposition, feature_id: str
) -> None:
    composition.then_cli_names_target_feature(FeatureId(feature_id))


# --- slice-02: caller-migration step vocabulary ------------------------------
# These decorators bind the slice-02-caller-migration.feature steps. Each
# step body is <=2 statements ending in a composition service call
# (Mandate-12 criterion 3); no control flow.


@given("the in-tree source roots src and scripts contain only migrated callers")
def given_in_tree_post_migration(composition: CommonAuditLogSsotComposition) -> None:
    composition.given_in_tree_post_migration_state()


@when(
    parsers.parse(
        "the production driving port for caller {caller_id} is invoked once for"
        ' feature "{feature_id}"'
    )
)
def when_caller_driving_port_invoked(
    composition: CommonAuditLogSsotComposition,
    caller_id: str,
    feature_id: str,
) -> None:
    composition.when_caller_driving_port_invoked(
        CALLER_ID_BY_PATH[caller_id],
        FeatureId(feature_id),
    )


@when("the per-feature ledger ban arch test is invoked without a source-roots override")
def when_arch_test_in_tree(composition: CommonAuditLogSsotComposition) -> None:
    composition.when_arch_test_runs_against_in_tree_roots()


@when(
    parsers.parse(
        "the legacy per-feature ledger appends a {event_kind} event for feature"
        ' "{feature_id}" slice "{slice_id}"'
    )
)
def when_legacy_appends(
    composition: CommonAuditLogSsotComposition,
    event_kind: str,
    feature_id: str,
    slice_id: str,
) -> None:
    composition.when_legacy_per_feature_writer_appends_event(
        EVENT_KIND_BY_PHRASE[event_kind],
        FeatureId(feature_id),
        SliceId(slice_id),
    )


@then("the common audit log file exists under the project repository")
def then_common_log_file_exists(composition: CommonAuditLogSsotComposition) -> None:
    composition.then_common_audit_log_file_exists()


@then(
    parsers.parse(
        'the per-feature ledger file for feature "{feature_id}" was not created'
    )
)
def then_per_feature_file_absent(
    composition: CommonAuditLogSsotComposition, feature_id: str
) -> None:
    composition.then_per_feature_ledger_file_absent(FeatureId(feature_id))


@then(
    parsers.parse(
        'the per-feature ledger file for feature "{feature_id}" exists under'
        " the project repository"
    )
)
def then_per_feature_file_exists(
    composition: CommonAuditLogSsotComposition, feature_id: str
) -> None:
    composition.then_per_feature_ledger_file_exists(FeatureId(feature_id))


@then("the arch test reports zero forbidden per-feature path literals")
def then_arch_test_zero_violations(
    composition: CommonAuditLogSsotComposition,
) -> None:
    composition.then_arch_test_reports_zero_violations()


@then(
    parsers.parse(
        "the legacy per-feature ledger round-trip returns exactly one record"
        ' carrying event "{event_kind}"'
    )
)
def then_legacy_round_trip(
    composition: CommonAuditLogSsotComposition, event_kind: str
) -> None:
    composition.then_legacy_per_feature_round_trip_returns_one_record(
        EVENT_KIND_BY_PHRASE[event_kind],
    )


# --- Given: substrate + recorded-event staging -------------------------------


@given("a fresh project repository with no atdd_pure audit log yet")
def given_fresh_repo(composition: CommonAuditLogSsotComposition) -> None:
    composition.given_fresh_project_repository()


@given(
    parsers.parse(
        "the common audit log has recorded a {event_kind} event for feature"
        ' "{feature_id}" slice "{slice_id}"'
    )
)
def given_recorded_event(
    composition: CommonAuditLogSsotComposition,
    event_kind: str,
    feature_id: str,
    slice_id: str,
) -> None:
    composition.given_recorded_event_for_feature(
        EVENT_KIND_BY_PHRASE[event_kind],
        FeatureId(feature_id),
        SliceId(slice_id),
    )


@given(
    "the recorded record has been tampered with a hand-edit that breaks its record hash"
)
def given_record_tampered(composition: CommonAuditLogSsotComposition) -> None:
    composition.given_recorded_record_tampered()


@given(
    parsers.parse(
        "a temporary source tree seeded with a caller in the {caller_scenario} shape"
    )
)
def given_arch_temp_tree(
    composition: CommonAuditLogSsotComposition, caller_scenario: str
) -> None:
    composition.given_arch_test_temp_tree(
        ARCH_CALLER_SCENARIO_BY_PHRASE[caller_scenario]
    )


# --- When: production driving-port invocations -------------------------------


@when(
    parsers.parse(
        "the common audit log writer appends a {event_kind} event for"
        ' feature "{feature_id}" slice "{slice_id}"'
    )
)
def when_writer_appends(
    composition: CommonAuditLogSsotComposition,
    event_kind: str,
    feature_id: str,
    slice_id: str,
) -> None:
    composition.when_writer_appends_event(
        EVENT_KIND_BY_PHRASE[event_kind],
        FeatureId(feature_id),
        SliceId(slice_id),
    )


@when(
    parsers.parse(
        'the operator queries the common audit log filtered by feature "{feature_id}"'
    )
)
def when_reader_queries(
    composition: CommonAuditLogSsotComposition, feature_id: str
) -> None:
    composition.when_reader_queries_filtered_by_feature(FeatureId(feature_id))


@when(
    parsers.parse(
        'the verify-integrity CLI is invoked on the project for feature "{feature_id}"'
    )
)
def when_cli_invoked(
    composition: CommonAuditLogSsotComposition, feature_id: str
) -> None:
    composition.when_verify_integrity_cli_runs(FeatureId(feature_id))


@when("the per-feature ledger ban arch test is invoked on the temporary source tree")
def when_arch_test_runs(composition: CommonAuditLogSsotComposition) -> None:
    composition.when_arch_test_runs_on_temp_tree()


# --- Then: universe-bound assertions over port-exposed observables -----------


@then(
    parsers.parse(
        'the common audit log contains exactly one record for feature "{feature_id}"'
    )
)
def then_log_one_record(
    composition: CommonAuditLogSsotComposition, feature_id: str
) -> None:
    composition.then_log_contains_exactly_one_record_for_feature(FeatureId(feature_id))


@then(
    parsers.parse(
        'that record carries event "{event_kind}" slice "{slice_id}"'
        " and a derived correlation identifier"
    )
)
def then_record_carries(
    composition: CommonAuditLogSsotComposition,
    event_kind: str,
    slice_id: str,
) -> None:
    composition.then_last_record_carries(
        EVENT_KIND_BY_PHRASE[event_kind],
        SliceId(slice_id),
    )


@then("exactly one record is returned")
def then_one_record_returned(composition: CommonAuditLogSsotComposition) -> None:
    composition.then_query_returned_exactly_one_record()


@then(parsers.parse('that record carries feature identifier "{feature_id}"'))
def then_record_carries_feature(
    composition: CommonAuditLogSsotComposition, feature_id: str
) -> None:
    composition.then_query_record_carries_feature(FeatureId(feature_id))


@then("the CLI exits with an integrity-violation verdict")
def then_cli_integrity_violation(
    composition: CommonAuditLogSsotComposition,
) -> None:
    composition.then_cli_reports_integrity_violation()


@then(parsers.parse('the verdict names the violation class as "{violation_class}"'))
def then_cli_class(
    composition: CommonAuditLogSsotComposition, violation_class: str
) -> None:
    composition.then_cli_names_violation_class(violation_class)


@then("the verdict names the offending line number")
def then_cli_line_number(composition: CommonAuditLogSsotComposition) -> None:
    composition.then_cli_names_offending_line_number()


@then("the verdict directs the operator to the repair instructions")
def then_cli_repair_doc(composition: CommonAuditLogSsotComposition) -> None:
    composition.then_cli_directs_to_repair_instructions()


@then(parsers.parse("the arch test verdict is {arch_verdict}"))
def then_arch_verdict(
    composition: CommonAuditLogSsotComposition, arch_verdict: str
) -> None:
    composition.then_arch_test_verdict_matches(ARCH_VERDICT_BY_PHRASE[arch_verdict])


# --- slice-02d-N0: shared seeding helper dual-shape step vocabulary ----------
# Two @when decorators drive the helper in legacy-shape vs singleton-shape via
# subprocess stubs (Mandate-13 boundary preserved). Four @then decorators
# assert the universe (file-system substrate, JSONL record count, explicit
# feature_id field membership) the AT-N0a / AT-N0b scenarios pin.


@when(
    parsers.parse(
        "the fixture helper seeds required feature-end records on a legacy-shape"
        ' ledger for feature "{feature_id}"'
    )
)
def when_helper_legacy_shape(
    composition: CommonAuditLogSsotComposition, feature_id: str
) -> None:
    composition.when_helper_seeds_legacy_shape_for_feature(FeatureId(feature_id))


@when(
    parsers.parse(
        "the fixture helper seeds required feature-end records on a singleton-shape"
        ' ledger for feature "{feature_id}" with feature_id forwarded'
    )
)
def when_helper_singleton_shape(
    composition: CommonAuditLogSsotComposition, feature_id: str
) -> None:
    composition.when_helper_seeds_singleton_shape_with_feature_id_forwarded(
        FeatureId(feature_id)
    )


@then("the common audit log file is not created")
def then_common_log_file_absent(
    composition: CommonAuditLogSsotComposition,
) -> None:
    composition.then_common_audit_log_file_absent()


@then(
    parsers.parse("exactly {count:d} records are seeded under the per-feature ledger")
)
def then_exactly_n_records_per_feature(
    composition: CommonAuditLogSsotComposition, count: int
) -> None:
    composition.then_exactly_n_records_under_per_feature_ledger(count)


@then(parsers.parse("exactly {count:d} records are seeded under the common audit log"))
def then_exactly_n_records_common_log(
    composition: CommonAuditLogSsotComposition, count: int
) -> None:
    composition.then_exactly_n_records_under_common_audit_log(count)


@then(
    parsers.parse(
        "every seeded record carries the ledger-bound feature_id field"
        ' "{expected_feature_id}"'
    )
)
def then_every_seeded_record_carries_ledger_bound_feature_id(
    composition: CommonAuditLogSsotComposition, expected_feature_id: str
) -> None:
    composition.then_every_seeded_record_carries_ledger_bound_feature_id(
        FeatureId(expected_feature_id)
    )


@then(
    parsers.parse(
        'every seeded record carries an explicit feature_id field "{expected_feature_id}"'
    )
)
def then_every_seeded_record_carries_feature_id(
    composition: CommonAuditLogSsotComposition, expected_feature_id: str
) -> None:
    composition.then_every_seeded_record_carries_explicit_feature_id(
        FeatureId(expected_feature_id)
    )


# --- slice-02c-A: gate-event affinity bundle step vocabulary ---------------
# Five decorators bind slice-02c-A-gate-event-affinity.feature. The
# parameterized templates dispatch through `SLICE_02C_A_CALLSITE_BY_PHRASE`
# so the parametrize Outline over 6 callsites reuses ONE @when decorator.
# Mandate-12 criterion 3 preserved: every body <=2 statements ending in a
# composition delegation, no control flow.

from .domain_types import SLICE_02C_A_CALLSITE_BY_PHRASE  # noqa: E402


@when(
    parsers.parse(
        'the slice-02c-A production driver for callsite "{slice_02c_a_callsite}"'
        ' is invoked once for feature "{feature_id}"'
    )
)
def when_slice_02c_a_driver_invoked(
    composition: CommonAuditLogSsotComposition,
    slice_02c_a_callsite: str,
    feature_id: str,
) -> None:
    composition.when_slice_02c_a_production_driver_invoked(
        SLICE_02C_A_CALLSITE_BY_PHRASE[slice_02c_a_callsite],
        FeatureId(feature_id),
    )


@then(
    parsers.parse(
        "the common audit log substrate exists under the project repository for"
        ' feature "{feature_id}"'
    )
)
def then_only_common_log_substrate(
    composition: CommonAuditLogSsotComposition, feature_id: str
) -> None:
    composition.then_only_common_log_substrate_present_for(FeatureId(feature_id))


@then(
    parsers.parse(
        'the per-feature legacy substrate for feature "{feature_id}" was not created'
    )
)
def then_no_per_feature_legacy_substrate(
    composition: CommonAuditLogSsotComposition, feature_id: str
) -> None:
    composition.then_per_feature_ledger_file_absent(FeatureId(feature_id))


@then(
    parsers.parse(
        'the operator sees exactly {count:d} records for feature "{feature_id}"'
    )
)
def then_operator_sees_n_records(
    composition: CommonAuditLogSsotComposition, count: int, feature_id: str
) -> None:
    composition.then_query_returned_exactly_n_records_for_feature(
        FeatureId(feature_id), count
    )


@then(
    parsers.parse(
        'no record returned for feature "{target_feature_id}" carries feature_id'
        ' "{other_feature_id}"'
    )
)
def then_no_cross_feature_leak(
    composition: CommonAuditLogSsotComposition,
    target_feature_id: str,
    other_feature_id: str,
) -> None:
    composition.then_query_returned_no_records_for_other_feature(
        FeatureId(target_feature_id), FeatureId(other_feature_id)
    )
