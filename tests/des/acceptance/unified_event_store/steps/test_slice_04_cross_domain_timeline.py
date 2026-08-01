"""Step definitions: one feature's events, merged into a single
chronological timeline.

unified-event-store slice-04 (DD-13, EXP-unified-event-store-3).

Driving surface (Owns-row correction, feature-delta.md [REF] Staging Plan):
every scenario drives `des event-store-query`'s default (no `--family`)
cross-domain mode via `des.cli.event_store_query.main(argv, output=)`
IN-PROCESS, over a fixture repo -- the composition-root driving port
(Mandate-16), never `CrossDomainReader.read_across()` directly. Step
bodies delegate to `CrossDomainReaderComposition`; no inline business logic
(Mandate-12 criterion 3).

active-RED scaffold (atdd_pure -- NOT `@skip`). At HEAD the CLI's
default-mode wiring calls the `CrossDomainReader` scaffold, whose
`read_across()` raises a bare `AssertionError` -- every scenario below
fails for that reason today, a semantic `AssertionError`, never a
collection/CLI-argument error (the composition catches it narrowly and
records it on the observable).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from des.domain.telemetry_paths import LedgerFamily

from .cross_domain_composition import CrossDomainReaderComposition


scenarios("../slice-04-cross-domain-timeline.feature")

_ALL_THREE_FAMILIES = (
    LedgerFamily.ATDD_PURE,
    LedgerFamily.EXAMINE,
    LedgerFamily.REVIEW,
)


@pytest.fixture
def composition() -> Iterator[CrossDomainReaderComposition]:
    """Fixture-repo composition root driving the real event-store-query CLI."""
    root = CrossDomainReaderComposition()
    try:
        yield root
    finally:
        root.restore_permissions()


# --- Given -----------------------------------------------------------------


@given(
    "a fixture feature with a slice-commit, an examine verdict, and a "
    "review verdict recorded across the three ledgers, in that "
    "chronological order"
)
def given_one_of_each_in_chronological_order(
    composition: CrossDomainReaderComposition, tmp_path: Path
) -> None:
    composition.given_fixture_repo(tmp_path, "demo-feature")
    composition.seed_record(
        LedgerFamily.ATDD_PURE,
        event="SliceCommitVerified",
        seq=1,
        timestamp="2026-07-31T10:00:00Z",
        slice_id="slice-01",
    )
    composition.seed_record(
        LedgerFamily.EXAMINE,
        event="ExamineVerdictRecorded",
        seq=1,
        timestamp="2026-07-31T10:00:01Z",
        slice_id="slice-01",
        verdict="PASS",
    )
    composition.seed_record(
        LedgerFamily.REVIEW,
        event="ReviewVerdictRecorded",
        seq=1,
        timestamp="2026-07-31T10:00:02Z",
        slice_id="slice-01",
        verdict="APPROVED",
    )


@given(
    "a fixture feature with 2 slice-commit events, 1 examine verdict, 1 "
    "review verdict, and 1 further review verdict re-recorded twice under "
    "one reduction key"
)
def given_several_records_no_silent_drop(
    composition: CrossDomainReaderComposition, tmp_path: Path
) -> None:
    # R48's own non-vacuity witness: 6 RAW lines, 5 distinct events. A wrong
    # raw-line-count implementation returns 6; the correct KEY-based law
    # (DD-7) collapses the re-recorded pair to 1 and returns 5 -- the two
    # laws DIVERGE on this fixture, unlike an all-legacy/all-distinct-key
    # fixture where they coincide by accident (the exact vacuity this
    # scenario exists to close).
    composition.given_fixture_repo(tmp_path, "demo-feature")
    seq = 0
    for i in range(2):
        seq += 1
        composition.seed_record(
            LedgerFamily.ATDD_PURE,
            event="SliceCommitVerified",
            seq=seq,
            timestamp=f"2026-07-31T10:{seq:02d}:00Z",
            slice_id=f"slice-{i + 1:02d}",
        )
    seq += 1
    composition.seed_record(
        LedgerFamily.EXAMINE,
        event="ExamineVerdictRecorded",
        seq=seq,
        timestamp=f"2026-07-31T10:{seq:02d}:00Z",
        slice_id="slice-01",
        verdict="PASS",
    )
    seq += 1
    composition.seed_record(
        LedgerFamily.REVIEW,
        event="ReviewVerdictRecorded",
        seq=seq,
        timestamp=f"2026-07-31T10:{seq:02d}:00Z",
        slice_id="slice-01",
        verdict="APPROVED",
    )
    composition.seed_derived_rows_sharing_key(
        LedgerFamily.REVIEW,
        reduction_key="rk-re-recorded-review",
        count=2,
        seq_start=seq + 1,
        timestamp_prefix="2026-07-31T11:",
    )


@given(
    "a fixture feature with 4 derived events sharing one reduction key recorded in the review ledger"
)
def given_shared_reduction_key(
    composition: CrossDomainReaderComposition, tmp_path: Path
) -> None:
    composition.given_fixture_repo(tmp_path, "demo-feature")
    composition.seed_derived_rows_sharing_key(
        LedgerFamily.REVIEW, reduction_key="rk-shared-review", count=4
    )


@given(
    "a fixture feature with one wrong-typed row in the atdd-pure ledger "
    "and a different wrong-typed row in the review ledger"
)
def given_two_distinct_family_faults(
    composition: CrossDomainReaderComposition, tmp_path: Path
) -> None:
    composition.given_fixture_repo(tmp_path, "demo-feature")
    composition.seed_derived_row_with_wrong_type_agent_id(
        LedgerFamily.ATDD_PURE,
        seq=1,
        timestamp="2026-07-31T12:00:00Z",
        reduction_key="rk-atdd-pure-fault",
    )
    composition.seed_derived_row_with_wrong_type_agent_id(
        LedgerFamily.REVIEW,
        seq=1,
        timestamp="2026-07-31T12:00:01Z",
        reduction_key="rk-review-fault",
    )


@given(
    "a fixture feature with events in all three ledgers, but the review ledger file is unreadable"
)
def given_review_ledger_unreadable(
    composition: CrossDomainReaderComposition, tmp_path: Path
) -> None:
    composition.given_fixture_repo(tmp_path, "demo-feature")
    composition.seed_record(
        LedgerFamily.ATDD_PURE,
        event="SliceCommitVerified",
        seq=1,
        timestamp="2026-07-31T13:00:00Z",
        slice_id="slice-01",
    )
    composition.seed_record(
        LedgerFamily.EXAMINE,
        event="ExamineVerdictRecorded",
        seq=1,
        timestamp="2026-07-31T13:00:01Z",
        slice_id="slice-01",
        verdict="PASS",
    )
    composition.seed_record(
        LedgerFamily.REVIEW,
        event="ReviewVerdictRecorded",
        seq=1,
        timestamp="2026-07-31T13:00:02Z",
        slice_id="slice-01",
        verdict="APPROVED",
    )
    composition.make_family_ledger_unreadable(LedgerFamily.REVIEW)


@given(
    "a fixture feature with a well-formed slice-commit event and, in the "
    "same ledger, one event whose agent id is a list instead of text"
)
def given_wrong_typed_row_among_well_formed_siblings(
    composition: CrossDomainReaderComposition, tmp_path: Path
) -> None:
    composition.given_fixture_repo(tmp_path, "demo-feature")
    composition.seed_record(
        LedgerFamily.ATDD_PURE,
        event="SliceCommitVerified",
        seq=1,
        timestamp="2026-07-31T14:00:00Z",
        slice_id="slice-01",
    )
    composition.seed_derived_row_with_wrong_type_agent_id(
        LedgerFamily.ATDD_PURE,
        seq=2,
        timestamp="2026-07-31T14:00:01Z",
        reduction_key="rk-atdd-pure-sibling-fault",
    )


@given(
    "a fixture feature with events in the atdd-pure and examine ledgers "
    "only, and no review ledger file at all"
)
def given_no_review_ledger_file(
    composition: CrossDomainReaderComposition, tmp_path: Path
) -> None:
    composition.given_fixture_repo(tmp_path, "demo-feature")
    composition.seed_record(
        LedgerFamily.ATDD_PURE,
        event="SliceCommitVerified",
        seq=1,
        timestamp="2026-07-31T15:00:00Z",
        slice_id="slice-01",
    )
    composition.seed_record(
        LedgerFamily.EXAMINE,
        event="ExamineVerdictRecorded",
        seq=1,
        timestamp="2026-07-31T15:00:01Z",
        slice_id="slice-01",
        verdict="PASS",
    )
    # deliberately no REVIEW family record -- absence, not a fault.


@given(
    "a fixture feature with an examine verdict and a review verdict recorded at the identical timestamp"
)
def given_tied_timestamp_across_families(
    composition: CrossDomainReaderComposition, tmp_path: Path
) -> None:
    # `seq` is DELIBERATELY distinct (1 vs 2) at the identical `timestamp` --
    # read_across's own declared sort key is `(timestamp, seq)` (feature-delta.md
    # [REF] Driving Ports), so `seq` is the DEFINED, stable secondary key this
    # scenario's Then step pins the resulting ORDER against (R55), not an
    # invented tie-break rule.
    composition.given_fixture_repo(tmp_path, "demo-feature")
    composition.seed_record(
        LedgerFamily.EXAMINE,
        event="ExamineVerdictRecorded",
        seq=1,
        timestamp="2026-07-31T16:00:00Z",
        slice_id="slice-01",
        verdict="PASS",
    )
    composition.seed_record(
        LedgerFamily.REVIEW,
        event="ReviewVerdictRecorded",
        seq=2,
        timestamp="2026-07-31T16:00:00Z",
        slice_id="slice-01",
        verdict="APPROVED",
    )


@given("a fixture feature with a review verdict recorded with no timestamp field")
def given_missing_timestamp(
    composition: CrossDomainReaderComposition, tmp_path: Path
) -> None:
    composition.given_fixture_repo(tmp_path, "demo-feature")
    composition.seed_record_without_timestamp(
        LedgerFamily.REVIEW,
        event="ReviewVerdictRecorded",
        seq=1,
        slice_id="slice-01",
        verdict="APPROVED",
    )


@given("a fixture feature with a review verdict recorded with a numeric timestamp")
def given_numeric_timestamp(
    composition: CrossDomainReaderComposition, tmp_path: Path
) -> None:
    composition.given_fixture_repo(tmp_path, "demo-feature")
    composition.seed_record_with_timestamp_value(
        LedgerFamily.REVIEW,
        event="ReviewVerdictRecorded",
        seq=1,
        timestamp=1753963200,
        slice_id="slice-01",
        verdict="APPROVED",
    )


@given(
    "a fixture feature with two events sharing one timestamp, one "
    "recorded with an integer seq and one recorded with a string seq"
)
def given_mismatched_seq_types_at_tied_timestamp(
    composition: CrossDomainReaderComposition, tmp_path: Path
) -> None:
    # R58's crash trigger: the sort key `(timestamp, seq)` only compares
    # the second component on a timestamp TIE -- a single wrong-typed seq
    # never crashes, so both rows MUST share the identical timestamp.
    composition.given_fixture_repo(tmp_path, "demo-feature")
    composition.seed_record(
        LedgerFamily.ATDD_PURE,
        event="SliceCommitVerified",
        seq=1,
        timestamp="2026-07-31T17:00:00Z",
        slice_id="slice-01",
    )
    composition.seed_record_with_seq_value(
        LedgerFamily.EXAMINE,
        event="ExamineVerdictRecorded",
        seq="2",
        timestamp="2026-07-31T17:00:00Z",
        slice_id="slice-01",
        verdict="PASS",
    )


@given(
    "a fixture feature with three events at the identical timestamp: "
    "seq -1, no seq field at all, and seq 1"
)
def given_seq_default_pinning_fixture(
    composition: CrossDomainReaderComposition, tmp_path: Path
) -> None:
    composition.given_fixture_repo(tmp_path, "demo-feature")
    composition.seed_record(
        LedgerFamily.ATDD_PURE,
        event="SliceCommitVerified",
        seq=-1,
        timestamp="2026-07-31T18:00:00Z",
        slice_id="slice-01",
    )
    composition.seed_record_without_seq(
        LedgerFamily.EXAMINE,
        event="ExamineVerdictRecorded",
        timestamp="2026-07-31T18:00:00Z",
        slice_id="slice-01",
        verdict="PASS",
    )
    composition.seed_record(
        LedgerFamily.REVIEW,
        event="ReviewVerdictRecorded",
        seq=1,
        timestamp="2026-07-31T18:00:00Z",
        slice_id="slice-01",
        verdict="APPROVED",
    )


# --- When --------------------------------------------------------------------


@when(
    "the orchestrator reads across the atdd-pure, examine, and review "
    "families for that feature"
)
def when_read_across_three_families(composition: CrossDomainReaderComposition) -> None:
    composition.when_read_across()


# --- Then ----------------------------------------------------------------------


@then("the merged timeline contains all three events in ascending chronological order")
def then_three_events_in_order(composition: CrossDomainReaderComposition) -> None:
    records = composition.observable().records
    assert records is not None, (
        "read_across must return a merged timeline with the 3 seeded events "
        f"in ascending timestamp order -- {composition.diag()}"
    )
    assert len(records) == 3, (
        f"the merged timeline must contain exactly the 3 seeded events -- {composition.diag()}"
    )
    timestamps = [record["timestamp"] for record in records]
    assert timestamps == sorted(timestamps), (
        "the merged timeline must be ordered by ascending timestamp -- got "
        f"{timestamps!r}. {composition.diag()}"
    )


@then("each row names which ledger family it came from")
def then_rows_tagged_with_source_family(
    composition: CrossDomainReaderComposition,
) -> None:
    records = composition.observable().records
    assert records is not None, (
        f"read_across must return a merged timeline before provenance can be checked -- {composition.diag()}"
    )
    valid_families = {family.value for family in _ALL_THREE_FAMILIES}
    for record in records:
        assert record.get("_source_family") in valid_families, (
            "every merged row must name its source ledger family via a "
            f"'_source_family' tag -- got {record!r}. {composition.diag()}"
        )


@then(
    "the merged timeline contains exactly 5 records, none of the 5 distinct "
    "events dropped, and the re-recorded review verdict counted once, not twice"
)
def then_no_silent_drop(composition: CrossDomainReaderComposition) -> None:
    records = composition.observable().records
    assert records is not None, (
        f"read_across must return a merged timeline -- {composition.diag()}"
    )
    # R48's non-vacuous witness: 6 RAW lines were seeded but only 5 DISTINCT
    # events exist (2 slice-commit + 1 examine + 1 review + 1 re-recorded
    # review pair collapsed to 1). A WRONG raw-line-count implementation
    # would report 6 here; this assertion fails against that wrong answer,
    # unlike the prior all-distinct-key fixture where both laws coincided.
    assert len(records) == 5, (
        "the merge must conserve DISTINCT events (post each family's own "
        "DD-7 dedup), never raw ledger lines -- expected 5 (the re-recorded "
        f"review verdict counts once, not twice), got {len(records)}. "
        f"{composition.diag()}"
    )
    matching = [r for r in records if r.get("reduction_key") == "rk-re-recorded-review"]
    assert len(matching) == 1, (
        "the re-recorded review verdict (2 raw rows sharing one "
        f"reduction_key) must collapse to exactly 1 record, got {len(matching)}. "
        f"{composition.diag()}"
    )


@then("the merged timeline contains exactly 1 record for that reduction key, not 4")
def then_shared_reduction_key_collapses_to_one(
    composition: CrossDomainReaderComposition,
) -> None:
    records = composition.observable().records
    assert records is not None, (
        f"read_across must return a merged timeline -- {composition.diag()}"
    )
    matching = [r for r in records if r.get("reduction_key") == "rk-shared-review"]
    assert len(matching) == 1, (
        "4 raw rows sharing one reduction_key must collapse to exactly 1 "
        f"accounting unit in the merged timeline (DD-7), got {len(matching)}. {composition.diag()}"
    )


@then(
    "the result carries a could-not-verify count of zero, present rather than omitted"
)
def then_arity_safe_zero(composition: CrossDomainReaderComposition) -> None:
    observable = composition.observable()
    assert observable.could_not_verify_count is not None, (
        f"read_across must return could_not_verify_count, present rather than omitted -- {composition.diag()}"
    )
    assert observable.could_not_verify_count == 0, (
        "every record in this fixture is well-formed, so "
        f"could_not_verify_count must be 0 -- {composition.diag()}"
    )
    assert observable.could_not_verify_reasons == [], (
        f"no could_not_verify reasons are expected here -- {composition.diag()}"
    )


@then("the result's could-not-verify count is 2")
def then_could_not_verify_count_is_two(
    composition: CrossDomainReaderComposition,
) -> None:
    observable = composition.observable()
    assert observable.could_not_verify_count is not None, (
        f"read_across must return could_not_verify_count -- {composition.diag()}"
    )
    assert observable.could_not_verify_count == 2, (
        "one wrong-typed row per family (2 families) must accumulate to "
        f"could_not_verify_count == 2, never reset between families -- {composition.diag()}"
    )


@then("the result names 2 distinct could-not-verify reasons, one per family")
def then_two_distinct_reasons(composition: CrossDomainReaderComposition) -> None:
    observable = composition.observable()
    reasons = observable.could_not_verify_reasons
    assert reasons is not None, (
        f"read_across must return could_not_verify_reasons -- {composition.diag()}"
    )
    assert len(reasons) == 2, (
        f"expected exactly 2 could_not_verify reasons (one per faulted family), got {len(reasons)}. {composition.diag()}"
    )
    assert len(set(reasons)) == 2, (
        f"the 2 reasons must be distinguishable, not duplicates -- {composition.diag()}"
    )
    # Attribution, not just distinctness (R51): each reason must name ITS OWN
    # family -- 2 distinct-but-SWAPPED reasons (atdd-pure's fault mislabeled
    # as review's, or vice versa) would satisfy the checks above and still be
    # wrong. A caller reading the merged reasons list must be able to tell
    # WHICH family each fault came from.
    atdd_pure_reasons = [r for r in reasons if "atdd-pure" in r.lower()]
    review_reasons = [r for r in reasons if "review" in r.lower()]
    assert len(atdd_pure_reasons) == 1, (
        "exactly 1 reason must name the atdd-pure family's own fault -- got "
        f"{atdd_pure_reasons!r} of {reasons!r}. {composition.diag()}"
    )
    assert len(review_reasons) == 1, (
        "exactly 1 reason must name the review family's own fault -- got "
        f"{review_reasons!r} of {reasons!r}. {composition.diag()}"
    )
    assert atdd_pure_reasons != review_reasons, (
        f"the atdd-pure and review reasons must not be interchangeable -- {composition.diag()}"
    )


@then("the merged timeline still contains the atdd-pure and examine events")
def then_healthy_families_still_present(
    composition: CrossDomainReaderComposition,
) -> None:
    records = composition.observable().records
    assert records is not None, (
        f"read_across must return a merged timeline even with one family's ledger unreadable -- {composition.diag()}"
    )
    events = {record["event"] for record in records}
    assert "SliceCommitVerified" in events and "ExamineVerdictRecorded" in events, (
        "the healthy atdd-pure and examine families' events must still appear "
        f"even when the review family's ledger is unreadable -- got {events!r}. {composition.diag()}"
    )


@then("the result's could-not-verify count names the review family's read failure")
def then_could_not_verify_names_review_failure(
    composition: CrossDomainReaderComposition,
) -> None:
    observable = composition.observable()
    assert observable.could_not_verify_count is not None, (
        f"read_across must return could_not_verify_count -- {composition.diag()}"
    )
    assert observable.could_not_verify_count >= 1, (
        f"the unreadable review ledger must raise could_not_verify_count -- {composition.diag()}"
    )
    reasons = observable.could_not_verify_reasons or []
    assert any("review" in reason.lower() for reason in reasons), (
        f"the could_not_verify reason must name the review family -- got {reasons!r}. {composition.diag()}"
    )


@then("the merged timeline still contains the well-formed slice-commit event")
def then_well_formed_sibling_still_present(
    composition: CrossDomainReaderComposition,
) -> None:
    records = composition.observable().records
    assert records is not None, (
        f"read_across must return a merged timeline even with a wrong-typed sibling row -- {composition.diag()}"
    )
    events = [r for r in records if r.get("event") == "SliceCommitVerified"]
    assert len(events) == 1, (
        "the well-formed slice-commit event must still appear even though "
        f"a wrong-typed row shares its ledger -- {composition.diag()}"
    )


@then("the result's could-not-verify count names the wrong-typed row")
def then_could_not_verify_names_wrong_typed_row(
    composition: CrossDomainReaderComposition,
) -> None:
    observable = composition.observable()
    assert observable.could_not_verify_count is not None, (
        f"read_across must return could_not_verify_count -- {composition.diag()}"
    )
    assert observable.could_not_verify_count >= 1, (
        f"the wrong-typed agent_id row must raise could_not_verify_count -- {composition.diag()}"
    )
    reasons = observable.could_not_verify_reasons or []
    assert any(
        "agent_id" in reason.lower() or "agent id" in reason.lower()
        for reason in reasons
    ), (
        "the could_not_verify reason must NAME the offending field "
        f"(agent_id) -- a generic reason cannot distinguish this fault "
        f"class from any other. got {reasons!r}. {composition.diag()}"
    )


@then("the merged timeline contains only the atdd-pure and examine events")
def then_only_present_families_contribute(
    composition: CrossDomainReaderComposition,
) -> None:
    records = composition.observable().records
    assert records is not None, (
        f"read_across must return a merged timeline -- {composition.diag()}"
    )
    events = {record["event"] for record in records}
    assert events == {"SliceCommitVerified", "ExamineVerdictRecorded"}, (
        "a family with no ledger file at all must contribute zero records "
        f"-- got {events!r}. {composition.diag()}"
    )


@then("the merged timeline contains both events, neither dropped as a duplicate")
def then_tied_timestamps_both_retained(
    composition: CrossDomainReaderComposition,
) -> None:
    records = composition.observable().records
    assert records is not None, (
        f"read_across must return a merged timeline -- {composition.diag()}"
    )
    assert len(records) == 2, (
        "two events tied on the identical timestamp must both be retained, "
        f"never dropped as a duplicate -- got {len(records)}. {composition.diag()}"
    )
    # R55: a tie on the PRIMARY sort key (timestamp) must break on a DEFINED,
    # STABLE secondary key -- read_across's own declared sort is
    # `(timestamp, seq)` (feature-delta.md [REF] Driving Ports), and the
    # fixture seeded seq=1 (examine) / seq=2 (review) at the identical
    # timestamp specifically so this order is pinned, not left to whatever a
    # nondeterministic merge (e.g. dict-iteration order) happens to produce.
    events_in_order = [record["event"] for record in records]
    assert events_in_order == ["ExamineVerdictRecorded", "ReviewVerdictRecorded"], (
        "a timestamp tie must break on the declared secondary key (seq): "
        "examine (seq=1) must sort before review (seq=2) -- got "
        f"{events_in_order!r}, never a nondeterministic order. {composition.diag()}"
    )


@then("the result's could-not-verify count names the missing timestamp")
def then_could_not_verify_names_missing_timestamp(
    composition: CrossDomainReaderComposition,
) -> None:
    observable = composition.observable()
    assert observable.could_not_verify_count is not None, (
        f"read_across must return could_not_verify_count -- {composition.diag()}"
    )
    assert observable.could_not_verify_count >= 1, (
        "a record with no timestamp field must raise could_not_verify_count "
        f"-- {composition.diag()}"
    )
    reasons = observable.could_not_verify_reasons or []
    assert any("timestamp" in reason.lower() for reason in reasons), (
        "the could_not_verify reason must NAME the ordering-key fault "
        f"(timestamp) -- a generic reason cannot distinguish this fault "
        f"class from any other. got {reasons!r}. {composition.diag()}"
    )
    assert any(
        "missing" in reason.lower() or "absent" in reason.lower() for reason in reasons
    ), (
        "the reason must name the fault as MISSING/ABSENT, not merely "
        f"wrong-typed -- got {reasons!r}. {composition.diag()}"
    )


@then("the result's could-not-verify count names the wrong-typed timestamp")
def then_could_not_verify_names_wrong_typed_timestamp(
    composition: CrossDomainReaderComposition,
) -> None:
    observable = composition.observable()
    assert observable.could_not_verify_count is not None, (
        f"read_across must return could_not_verify_count -- {composition.diag()}"
    )
    assert observable.could_not_verify_count >= 1, (
        "a record whose timestamp is a number, not text, must raise "
        f"could_not_verify_count -- {composition.diag()}"
    )
    reasons = observable.could_not_verify_reasons or []
    assert any("timestamp" in reason.lower() for reason in reasons), (
        "the could_not_verify reason must NAME the ordering-key field "
        f"(timestamp) -- a generic reason cannot distinguish this fault "
        f"class from any other. got {reasons!r}. {composition.diag()}"
    )
    assert any(
        keyword in reason.lower()
        for reason in reasons
        for keyword in ("type", "not text", "not str", "number", "int", "float")
    ), (
        "the reason must positively name the WRONG-TYPE nature of the "
        "fault (a number where text was required), not merely mention "
        f"'timestamp' in isolation -- got {reasons!r}. {composition.diag()}"
    )


@then("that reason is distinguishable from a missing-timestamp reason")
def then_wrong_type_reason_distinct_from_missing(
    composition: CrossDomainReaderComposition,
) -> None:
    observable = composition.observable()
    reasons = observable.could_not_verify_reasons
    assert reasons is not None and len(reasons) >= 1, (
        f"read_across must return at least one could_not_verify reason -- {composition.diag()}"
    )
    assert not any("missing" in reason.lower() for reason in reasons), (
        "a wrong-TYPED timestamp's reason must be distinct from a "
        f"missing-timestamp reason -- got {reasons!r}. {composition.diag()}"
    )


@then("the query does not crash and the exit code is 0")
def then_query_does_not_crash(composition: CrossDomainReaderComposition) -> None:
    observable = composition.observable()
    assert observable.unhandled_exception is None, (
        "a timestamp tie with mismatched seq types must degrade into "
        "could_not_verify, never crash the merge's sort with an uncaught "
        f"exception -- {composition.diag()}"
    )
    assert observable.exit_code == 0, (
        f"the query must complete with exit code 0 -- {composition.diag()}"
    )


@then(
    "the result's could-not-verify count names the seq field and its "
    "wrong type, distinguishable from the timestamp reasons"
)
def then_could_not_verify_names_wrong_typed_seq(
    composition: CrossDomainReaderComposition,
) -> None:
    observable = composition.observable()
    assert observable.could_not_verify_count is not None, (
        f"read_across must return could_not_verify_count -- {composition.diag()}"
    )
    assert observable.could_not_verify_count == 1, (
        "exactly the string-typed seq row (tied on timestamp with an "
        f"int-typed sibling) must raise could_not_verify_count -- {composition.diag()}"
    )
    reasons = observable.could_not_verify_reasons or []
    seq_reasons = [r for r in reasons if "seq" in r.lower()]
    assert len(seq_reasons) == 1, (
        "the could_not_verify reason must NAME the offending field (seq) "
        "-- a generic reason cannot distinguish this fault class from the "
        f"timestamp faults (R56/R57). got {reasons!r}. {composition.diag()}"
    )
    assert any(
        keyword in reason.lower()
        for reason in seq_reasons
        for keyword in ("type", "not int", "not str", "string", "str", "int")
    ), (
        "the reason must positively name the WRONG-TYPE nature of the seq "
        f"fault -- got {seq_reasons!r}. {composition.diag()}"
    )
    assert not any("timestamp" in reason.lower() for reason in seq_reasons), (
        "a wrong-typed-seq reason must be distinguishable from the "
        "timestamp-missing (R56) / timestamp-wrong-typed (R57) reasons -- "
        f"got {seq_reasons!r}. {composition.diag()}"
    )


@then(
    "the merged timeline still contains the well-formed sibling event, "
    "counted in the measured count"
)
def then_well_formed_seq_sibling_survives(
    composition: CrossDomainReaderComposition,
) -> None:
    observable = composition.observable()
    records = observable.records
    assert records is not None, (
        "read_across must return a merged timeline even with a "
        f"wrong-typed seq sibling -- {composition.diag()}"
    )
    events = [r for r in records if r.get("event") == "SliceCommitVerified"]
    assert len(events) == 1, (
        "the well-formed int-seq sibling must still appear even though "
        "its tied-timestamp partner has a string-typed seq -- "
        f"{composition.diag()}"
    )
    assert observable.measured_count == 1, (
        "the well-formed sibling must be the only record counted in "
        f"measured_count -- {composition.diag()}"
    )


@then("the merged timeline contains all three events, each counted as measured")
def then_all_three_seq_default_events_measured(
    composition: CrossDomainReaderComposition,
) -> None:
    observable = composition.observable()
    records = observable.records
    assert records is not None, (
        f"read_across must return a merged timeline -- {composition.diag()}"
    )
    assert len(records) == 3, (
        "an absent seq must not disqualify its record -- all 3 events "
        f"(including the no-seq one) must appear, got {len(records)}. {composition.diag()}"
    )
    assert observable.measured_count == 3, (
        "the no-seq event is a legitimate measured record, not a "
        "could_not_verify -- expected measured_count == 3, got "
        f"{observable.measured_count}. {composition.diag()}"
    )
    assert observable.could_not_verify_count == 0, (
        "an absent seq alone must never raise could_not_verify -- got "
        f"{observable.could_not_verify_count}. {composition.diag()}"
    )


@then(
    "the merged order is seq -1, then the no-seq event, then seq 1, "
    "pinning the absent seq to sort as zero"
)
def then_seq_default_order_pinned(
    composition: CrossDomainReaderComposition,
) -> None:
    records = composition.observable().records
    assert records is not None, (
        f"read_across must return a merged timeline -- {composition.diag()}"
    )
    events_in_order = [record["event"] for record in records]
    assert events_in_order == [
        "SliceCommitVerified",
        "ExamineVerdictRecorded",
        "ReviewVerdictRecorded",
    ], (
        "a timestamp tie among seq -1, an absent seq, and seq 1 must sort "
        "in that order -- proving the absent seq defaults to exactly 0 "
        "(between -1 and 1), not merely 'some smaller-than-1 value' -- got "
        f"{events_in_order!r}. {composition.diag()}"
    )
