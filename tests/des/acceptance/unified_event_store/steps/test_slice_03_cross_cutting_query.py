"""Step definitions: a cross-cutting query caller gets one merged view with
an honest could-not-verify count.

unified-event-store slice-03 (DD-7/DD-8/DD-9/DD-10, EXP-unified-event-store-2).

Layer 2 in-process (Mandate 13 L2 default, content facet) -- no new
@walking_skeleton (the feature's one subprocess-E2E WS already lives in
slice-02). Example-only, no PBT machinery (Mandate 11 -- sad paths at this
layer stay example-based); the Scenario Outline's 3 rows enumerate the
legacy-only / new-envelope-only / mixed populations the cutover criterion
names.

Step bodies delegate to `EventStoreQueryComposition`; no inline business
logic (Mandate-12 criterion 3).

Status (updated post-DELIVER, code-review round): the first 7 scenarios are
GREEN against the real `des.cli.event_store_query` implementation. The two
scenarios added afterward (malformed / non-object ledger line) are RED at
HEAD for a REAL bug, not a scaffold: `UnifiedEventStoreAdapter.read()` does
not defend against a corrupted line inside an otherwise-readable ledger
file, so it raises uncaught instead of contributing to
`could_not_verify_count`. The composition catches that crash into
`unhandled_exception` on the observable, so `Then the query completes
without crashing` fails with a clean, business-meaningful assertion --
never a bare traceback escaping the test.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .query_composition import EventStoreQueryComposition


scenarios("../slice-03-cross-cutting-query.feature")


@pytest.fixture
def composition() -> Iterator[EventStoreQueryComposition]:
    """Production-wired composition root driving the real event-store-query CLI."""
    root = EventStoreQueryComposition()
    try:
        yield root
    finally:
        root.restore_permissions()


def _parse_last_json_line(text: str) -> dict[str, Any] | None:
    """The last well-formed single-line JSON object in `text`, or `None`.

    Mirrors the parsing shape `test_slice_02_startup_refusal.py` already
    uses for the probe's refusal payload -- one JSON object per emitted
    line, never multiple objects concatenated on one line."""
    payload: dict[str, Any] | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            candidate = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            payload = candidate
    return payload


# --- Given -----------------------------------------------------------------


@given(
    parsers.parse(
        'the cross-cutting query caller has a real repo with a "{family}" '
        "ledger holding {legacy_count:d} legacy row(s) and {derived_count:d} "
        'new-envelope row(s) for partition key "{partition_key}"'
    )
)
def given_mixed_ledger(
    composition: EventStoreQueryComposition,
    tmp_path: Path,
    family: str,
    legacy_count: int,
    derived_count: int,
    partition_key: str,
) -> None:
    composition.given_repo_root(tmp_path)
    composition.given_ledger(family, partition_key, legacy_count, derived_count)


@given(
    parsers.parse(
        "the cross-cutting query caller has a real repo with an empty "
        '"{family}" ledger file for partition key "{partition_key}"'
    )
)
def given_empty_ledger(
    composition: EventStoreQueryComposition,
    tmp_path: Path,
    family: str,
    partition_key: str,
) -> None:
    composition.given_repo_root(tmp_path)
    composition.given_empty_ledger_file(family, partition_key)


@given(
    parsers.parse(
        "the cross-cutting query caller's repo has no ledger file at all "
        'for partition key "{partition_key}"'
    )
)
def given_no_ledger_file(
    composition: EventStoreQueryComposition,
    tmp_path: Path,
    partition_key: str,
) -> None:
    composition.given_repo_root(tmp_path)
    composition.given_no_ledger_file()


@given(
    "the ledger file itself has been made unreadable inside the caller's own sandbox"
)
def given_ledger_file_unreadable(composition: EventStoreQueryComposition) -> None:
    composition.given_ledger_file_unreadable()


@given("the ledger also holds one truncated (malformed JSON) line")
def given_malformed_line_appended(composition: EventStoreQueryComposition) -> None:
    composition.given_malformed_line_appended()


@given("the ledger also holds one row that is valid JSON but not a JSON object")
def given_non_object_row_appended(composition: EventStoreQueryComposition) -> None:
    composition.given_non_object_row_appended()


@given("the ledger also holds one derived row with no agent_id key at all")
def given_derived_row_missing_agent_id_appended(
    composition: EventStoreQueryComposition,
) -> None:
    composition.given_derived_row_missing_agent_id_appended()


@given("the ledger also holds one derived row with no reduction_seq key at all")
def given_derived_row_missing_reduction_seq_appended(
    composition: EventStoreQueryComposition,
) -> None:
    composition.given_derived_row_missing_reduction_seq_appended()


# --- Given (DD-17 round-4: ADR-EVT-002 row-recognition contract) -----------


@given(
    parsers.parse("the ledger also holds one row whose top-level JSON value is {shape}")
)
def given_gate0_non_dict_row_appended(
    composition: EventStoreQueryComposition, shape: str
) -> None:
    composition.given_gate0_non_dict_row_appended(shape)


@given(
    parsers.parse(
        "the ledger also holds one primary-new row whose agent_id is {wrong_type}"
    )
)
def given_primary_new_row_with_wrong_type_agent_id_appended(
    composition: EventStoreQueryComposition, wrong_type: str
) -> None:
    composition.given_primary_new_row_with_wrong_type_agent_id_appended(wrong_type)


@given(
    parsers.parse(
        "the ledger also holds one derived row whose agent_id is {wrong_type}"
    )
)
def given_derived_row_with_wrong_type_agent_id_appended(
    composition: EventStoreQueryComposition, wrong_type: str
) -> None:
    composition.given_derived_row_with_wrong_type_agent_id_appended(wrong_type)


@given(
    parsers.parse(
        "the ledger also holds one derived row whose reduction_key is {wrong_value}"
    )
)
def given_derived_row_with_wrong_reduction_key_appended(
    composition: EventStoreQueryComposition, wrong_value: str
) -> None:
    composition.given_derived_row_with_wrong_reduction_key_appended(wrong_value)


@given(
    parsers.parse(
        "the ledger also holds one derived row whose reduction_seq is {wrong_value}"
    )
)
def given_derived_row_with_wrong_reduction_seq_appended(
    composition: EventStoreQueryComposition, wrong_value: str
) -> None:
    composition.given_derived_row_with_wrong_reduction_seq_appended(wrong_value)


@given(
    "the ledger also holds one derived row whose agent_id, reduction_key, and "
    "reduction_seq are all the wrong type at once"
)
def given_derived_row_with_all_three_fields_wrong_appended(
    composition: EventStoreQueryComposition,
) -> None:
    composition.given_derived_row_with_all_three_fields_wrong_appended()


@given(
    "the ledger also holds one derived row, alone in its reduction_key group, "
    "whose reduction_seq is NaN"
)
def given_derived_row_alone_in_its_group_with_nan_reduction_seq_appended(
    composition: EventStoreQueryComposition,
) -> None:
    composition.given_derived_row_alone_in_its_group_with_nan_reduction_seq_appended()


@given("the ledger file itself has been corrupted with invalid UTF-8 bytes")
def given_ledger_file_corrupted_with_invalid_utf8(
    composition: EventStoreQueryComposition,
) -> None:
    composition.given_ledger_file_corrupted_with_invalid_utf8()


@given(
    "the ledger also holds one line with an integer literal beyond CPython's "
    "int-string conversion limit"
)
def given_line_with_oversized_integer_literal_appended(
    composition: EventStoreQueryComposition,
) -> None:
    composition.given_line_with_oversized_integer_literal_appended()


@given("the ledger also holds one line with extreme JSON nesting depth")
def given_line_with_extreme_nesting_depth_appended(
    composition: EventStoreQueryComposition,
) -> None:
    composition.given_line_with_extreme_nesting_depth_appended()


@given(
    parsers.parse(
        "the ledger also holds {count:d} derived rows sharing one reduction "
        "key with a single unambiguous winner"
    )
)
def given_derived_rows_sharing_one_reduction_key_appended(
    composition: EventStoreQueryComposition, count: int
) -> None:
    composition.given_derived_rows_sharing_one_reduction_key_appended(count)


# --- When --------------------------------------------------------------------


@when(
    parsers.parse(
        'the cross-cutting query caller queries family "{family}" '
        'partition key "{partition_key}"'
    )
)
def when_query(
    composition: EventStoreQueryComposition, family: str, partition_key: str
) -> None:
    composition.when_query(family, partition_key)


# --- Then --------------------------------------------------------------------


@then(parsers.parse("the query reports {expected_measured:d} measured record(s)"))
def then_reports_measured(
    composition: EventStoreQueryComposition, expected_measured: int
) -> None:
    obs = composition.observable("unified-event-store")
    payload = _parse_last_json_line(obs.captured_output)
    assert payload is not None, (
        "the query must emit exactly one JSON answer carrying measured_count "
        f"-- none was captured. {composition.diag('unified-event-store')}"
    )
    assert payload.get("measured_count") == expected_measured, (
        f"expected measured_count={expected_measured!r}, got "
        f"{payload.get('measured_count')!r}. "
        f"{composition.diag('unified-event-store')}"
    )


@then("every returned record is tagged with the generation it came from")
def then_every_record_tagged(composition: EventStoreQueryComposition) -> None:
    obs = composition.observable("unified-event-store")
    payload = _parse_last_json_line(obs.captured_output)
    assert payload is not None, (
        "the query must emit a JSON answer carrying tagged records -- none "
        f"was captured. {composition.diag('unified-event-store')}"
    )
    records = payload.get("records", [])
    assert records, (
        "expected at least one record in the merged result -- got an empty "
        f"records list. {composition.diag('unified-event-store')}"
    )
    for record in records:
        generation = record.get("envelope_generation")
        assert generation in {"legacy", "new"}, (
            f"record {record!r} is missing a recognized envelope_generation "
            "tag ('legacy' or 'new') -- a merged-but-untagged result is a "
            f"FAIL. {composition.diag('unified-event-store')}"
        )


@then(
    "the single reported output carries both a measured count and a "
    "could-not-verify count in the same answer"
)
def then_total_and_could_not_verify_travel_together(
    composition: EventStoreQueryComposition,
) -> None:
    obs = composition.observable("unified-event-store")
    payload = _parse_last_json_line(obs.captured_output)
    assert payload is not None, (
        "the query must emit a JSON answer -- none was captured. "
        f"{composition.diag('unified-event-store')}"
    )
    assert "measured_count" in payload and "could_not_verify_count" in payload, (
        "a bare total -- one without its could-not-verify companion in the "
        "SAME answer -- is the exact defect this slice exists to prevent, "
        f"even when the total happens to be correct. {composition.diag('unified-event-store')}"
    )


@then(
    "the caller never has to issue a second query to learn the could-not-verify count"
)
def then_no_second_query_needed(composition: EventStoreQueryComposition) -> None:
    """Structural half (peer-review finding, closed -- distinct from the
    payload-shape check above, not a duplicate of it): assert this TEST
    ITSELF issued exactly ONE `when_query` call for this partition key --
    proving no second invocation was needed to complete the scenario,
    rather than merely re-reading the same JSON object a second time."""
    count = composition.query_count("unified-event-store")
    assert count == 1, (
        "the scenario itself must complete on exactly one query -- got "
        f"{count} invocation(s) for partition key 'unified-event-store'."
    )


@then(
    "the could-not-verify count is raised, naming a reason, rather than "
    "the measured total silently dropping"
)
def then_could_not_verify_raised_with_reason(
    composition: EventStoreQueryComposition,
) -> None:
    obs = composition.observable("unified-event-store")
    payload = _parse_last_json_line(obs.captured_output)
    assert payload is not None, (
        "the query must emit a JSON answer even when the ledger file is "
        f"unreadable. {composition.diag('unified-event-store')}"
    )
    assert payload.get("could_not_verify_count", 0) >= 1, (
        "an unreadable ledger file must raise could_not_verify_count -- "
        "never silently drop the measured total by one instead. "
        f"{composition.diag('unified-event-store')}"
    )
    reasons = payload.get("could_not_verify_reasons", [])
    assert reasons, (
        "a raised could_not_verify_count must come with at least one named "
        f"reason, not a bare number. {composition.diag('unified-event-store')}"
    )
    # Negative-oracle half (peer-review finding, closed): the 2 legacy rows
    # this fixture wrote sit inside the now-unreadable file, so NONE of
    # them can honestly be measured. A measured_count > 0 here would mean
    # the query silently read past the fault for some rows and shrank
    # only the could-not-verify side to compensate -- exactly the
    # smaller-but-wrong total the charter names as the central failure.
    assert payload.get("measured_count") == 0, (
        "an unreadable ledger file must not report ANY of its rows as "
        "measured -- a nonzero measured_count here would itself be a "
        "silent (partial) undercount of the could-not-verify population. "
        f"got measured_count={payload.get('measured_count')!r}. "
        f"{composition.diag('unified-event-store')}"
    )


@then("the two answers are distinguishable")
def then_two_answers_distinguishable(composition: EventStoreQueryComposition) -> None:
    empty_obs = composition.observable("genuinely-empty-feature")
    absent_obs = composition.observable("never-queried-feature")
    empty_payload = _parse_last_json_line(empty_obs.captured_output)
    absent_payload = _parse_last_json_line(absent_obs.captured_output)
    assert empty_payload is not None, (
        "the genuinely-empty-ledger query must emit a JSON answer -- "
        f"{composition.diag('genuinely-empty-feature')}"
    )
    assert absent_payload is not None, (
        "the never-queried (absent-ledger) query must emit a JSON answer "
        f"-- {composition.diag('never-queried-feature')}"
    )
    assert empty_payload != absent_payload, (
        "a query against a genuinely-empty ledger and a query against an "
        "absent ledger must NOT report the identical answer -- absence of "
        "evidence and never-looked must be told apart, or the store cannot "
        "tell 'nothing happened' from 'I never looked'."
    )


@then(
    parsers.parse(
        'the "{partition_key}" answer reports zero measured records with '
        "zero could-not-verify"
    )
)
def then_answer_reports_zero(
    composition: EventStoreQueryComposition, partition_key: str
) -> None:
    payload = _parse_last_json_line(
        composition.observable(partition_key).captured_output
    )
    assert payload is not None, (
        f"expected a JSON answer for {partition_key!r} -- "
        f"{composition.diag(partition_key)}"
    )
    assert payload.get("measured_count") == 0, (
        f"expected measured_count=0 for a genuinely-empty ledger, got "
        f"{payload.get('measured_count')!r}. {composition.diag(partition_key)}"
    )
    assert payload.get("could_not_verify_count") == 0, (
        "a genuinely-empty (but present) ledger file must not itself count "
        f"as could-not-verify. {composition.diag(partition_key)}"
    )


@then(
    parsers.parse(
        'the "{partition_key}" answer names a could-not-verify reason for '
        "the absent ledger"
    )
)
def then_answer_names_absent_reason(
    composition: EventStoreQueryComposition, partition_key: str
) -> None:
    payload = _parse_last_json_line(
        composition.observable(partition_key).captured_output
    )
    assert payload is not None, (
        f"expected a JSON answer for {partition_key!r} -- "
        f"{composition.diag(partition_key)}"
    )
    assert payload.get("could_not_verify_count", 0) >= 1, (
        "querying a partition key with NO ledger file at all must raise "
        "could_not_verify_count -- a query against absence must never "
        f"report success as if it had found zero events. {composition.diag(partition_key)}"
    )
    reasons = payload.get("could_not_verify_reasons", [])
    assert any(
        "absent" in reason.lower()
        or "no ledger" in reason.lower()
        or "not found" in reason.lower()
        for reason in reasons
    ), (
        "expected a could_not_verify reason naming the absent ledger file, "
        f"got {reasons!r}. {composition.diag(partition_key)}"
    )


@then("the telemetry root is left with the same entries it started with")
def then_no_mutation(composition: EventStoreQueryComposition) -> None:
    from tests.common.state_delta import assert_state_delta, unchanged

    assert_state_delta(
        before={"telemetry_root.listing": composition.telemetry_root_listing_before()},
        after={"telemetry_root.listing": composition.telemetry_root_listing()},
        universe={"telemetry_root.listing"},
        expected={"telemetry_root.listing": unchanged()},
    )


@then("the query completes without crashing")
def then_completes_without_crashing(composition: EventStoreQueryComposition) -> None:
    """Code-review gap (closed here): a corrupted ledger line must degrade
    LOUD into could_not_verify_count, never crash the query with an
    uncaught exception -- the same "never silent-wrong, never a crash"
    family as the unreadable-ledger-file scenario above."""
    obs = composition.observable("unified-event-store")
    assert obs.unhandled_exception is None, (
        "the query must not crash on a corrupted ledger line -- it must "
        "degrade into a controlled could_not_verify answer instead. got "
        f"an unhandled {obs.unhandled_exception}. {composition.diag('unified-event-store')}"
    )


@then(
    "the could-not-verify count names a reason identifying a malformed "
    "ledger line, distinguishable from an unreadable-file reason"
)
def then_malformed_line_reason(composition: EventStoreQueryComposition) -> None:
    obs = composition.observable("unified-event-store")
    payload = _parse_last_json_line(obs.captured_output)
    assert payload is not None, (
        "the query must emit a JSON answer even when one ledger line is "
        f"malformed. {composition.diag('unified-event-store')}"
    )
    assert payload.get("could_not_verify_count", 0) >= 1, (
        "a malformed (truncated) ledger line must raise could_not_verify_count "
        f"-- it must never be silently dropped or silently counted as "
        f"measured. {composition.diag('unified-event-store')}"
    )
    reasons = payload.get("could_not_verify_reasons", [])
    assert reasons, (
        "a raised could_not_verify_count must come with at least one named "
        f"reason. {composition.diag('unified-event-store')}"
    )
    assert not any("could not be read" in reason.lower() for reason in reasons), (
        "a malformed LINE inside a READABLE file must be reported with a "
        "DIFFERENT reason than an unreadable FILE -- collapsing the two "
        "would repeat, one level down, exactly the honesty failure this "
        f"charter is about. got {reasons!r}. {composition.diag('unified-event-store')}"
    )
    assert any(
        "malformed" in reason.lower()
        or "invalid json" in reason.lower()
        or "could not parse" in reason.lower()
        or "parse" in reason.lower()
        for reason in reasons
    ), (
        "expected a reason identifying a malformed/unparsable ledger line, "
        f"got {reasons!r}. {composition.diag('unified-event-store')}"
    )


@then(
    "the could-not-verify count names a reason identifying a non-object "
    "ledger row, distinguishable from an unreadable-file reason"
)
def then_non_object_row_reason(composition: EventStoreQueryComposition) -> None:
    obs = composition.observable("unified-event-store")
    payload = _parse_last_json_line(obs.captured_output)
    assert payload is not None, (
        "the query must emit a JSON answer even when one ledger row is "
        f"valid JSON but not an object. {composition.diag('unified-event-store')}"
    )
    assert payload.get("could_not_verify_count", 0) >= 1, (
        "a valid-JSON-but-not-an-object ledger row must raise "
        "could_not_verify_count -- it must never be silently dropped or "
        f"silently counted as measured. {composition.diag('unified-event-store')}"
    )
    reasons = payload.get("could_not_verify_reasons", [])
    assert reasons, (
        "a raised could_not_verify_count must come with at least one named "
        f"reason. {composition.diag('unified-event-store')}"
    )
    assert not any("could not be read" in reason.lower() for reason in reasons), (
        "a wrong-shape ROW inside a READABLE file must be reported with a "
        "DIFFERENT reason than an unreadable FILE. got "
        f"{reasons!r}. {composition.diag('unified-event-store')}"
    )
    assert any(
        "not a json object" in reason.lower()
        or "not an object" in reason.lower()
        or "unexpected shape" in reason.lower()
        or "not a mapping" in reason.lower()
        for reason in reasons
    ), (
        "expected a reason identifying a ledger row that is not a JSON "
        f"object, got {reasons!r}. {composition.diag('unified-event-store')}"
    )


@then("the query exits with status 0")
def then_exit_code_zero(composition: EventStoreQueryComposition) -> None:
    obs = composition.observable("unified-event-store")
    assert obs.exit_code == 0, (
        "a degraded-but-honest could-not-verify answer must still exit 0 "
        "-- the query completed and reported honestly, it did not fail to "
        f"run. {composition.diag('unified-event-store')}"
    )


@then(
    "the could-not-verify count names a reason identifying a derived row "
    "missing its agent_id key entirely, distinguishable from a "
    "null-agent_id reason, a malformed-line reason, a non-object-row "
    "reason, and an unreadable-file reason"
)
def then_missing_agent_id_key_reason(
    composition: EventStoreQueryComposition,
) -> None:
    """Round-3 regression (D1 one layer deeper): a derived row missing the
    `agent_id` KEY ENTIRELY must degrade into a NAMED reason distinguishable
    from all four sibling reasons already covered -- most importantly the
    DD-8 null-agent_id reason, since ABSENT and NULL are genuinely different
    faults that must not be conflated in the reported string."""
    obs = composition.observable("unified-event-store")
    payload = _parse_last_json_line(obs.captured_output)
    assert payload is not None, (
        "the query must emit a JSON answer even when one derived row is "
        f"missing its agent_id key. {composition.diag('unified-event-store')}"
    )
    assert payload.get("could_not_verify_count", 0) >= 1, (
        "a derived row missing its agent_id key entirely must raise "
        "could_not_verify_count -- it must never be silently dropped or "
        f"silently counted as measured. {composition.diag('unified-event-store')}"
    )
    reasons = payload.get("could_not_verify_reasons", [])
    assert reasons, (
        "a raised could_not_verify_count must come with at least one named "
        f"reason. {composition.diag('unified-event-store')}"
    )
    lowered = [reason.lower() for reason in reasons]
    assert not any("could not be read" in reason for reason in lowered), (
        "a missing-KEY row inside a READABLE file must be reported with a "
        "DIFFERENT reason than an unreadable FILE. got "
        f"{reasons!r}. {composition.diag('unified-event-store')}"
    )
    assert not any(
        "malformed" in reason or "could not parse" in reason for reason in lowered
    ), (
        "a missing-KEY row must be reported with a DIFFERENT reason than a "
        f"malformed/unparsable ledger LINE. got {reasons!r}. "
        f"{composition.diag('unified-event-store')}"
    )
    assert not any(
        "not a json object" in reason or "not an object" in reason for reason in lowered
    ), (
        "a missing-KEY row must be reported with a DIFFERENT reason than a "
        f"valid-JSON-but-non-object ROW. got {reasons!r}. "
        f"{composition.diag('unified-event-store')}"
    )
    assert not any("null agent_id" in reason for reason in lowered), (
        "a row with agent_id ABSENT ENTIRELY must be reported with a "
        "DIFFERENT reason than DD-8's agent_id-present-but-NULL case -- "
        "ABSENT and NULL are distinct faults and must not be conflated. "
        f"got {reasons!r}. {composition.diag('unified-event-store')}"
    )
    assert any(
        "agent_id" in reason
        and ("missing" in reason or "absent" in reason or "no agent_id" in reason)
        for reason in lowered
    ), (
        "expected a reason identifying a derived row missing its agent_id "
        f"key entirely, got {reasons!r}. {composition.diag('unified-event-store')}"
    )


@then(
    "the could-not-verify count names a reason identifying a derived row "
    "missing its reduction_seq key entirely, distinguishable from an "
    "ambiguous-tied-max reason, a malformed-line reason, a non-object-row "
    "reason, and an unreadable-file reason"
)
def then_missing_reduction_seq_key_reason(
    composition: EventStoreQueryComposition,
) -> None:
    """Sibling to the agent_id case above -- a distinct code path
    (`max(r["reduction_seq"] for r in group)`) but the same defect class
    and the same never-crash, always-name-it-distinguishably obligation."""
    obs = composition.observable("unified-event-store")
    payload = _parse_last_json_line(obs.captured_output)
    assert payload is not None, (
        "the query must emit a JSON answer even when one derived row is "
        "missing its reduction_seq key. "
        f"{composition.diag('unified-event-store')}"
    )
    assert payload.get("could_not_verify_count", 0) >= 1, (
        "a derived row missing its reduction_seq key entirely must raise "
        "could_not_verify_count -- it must never be silently dropped or "
        f"silently counted as measured. {composition.diag('unified-event-store')}"
    )
    reasons = payload.get("could_not_verify_reasons", [])
    assert reasons, (
        "a raised could_not_verify_count must come with at least one named "
        f"reason. {composition.diag('unified-event-store')}"
    )
    lowered = [reason.lower() for reason in reasons]
    assert not any("could not be read" in reason for reason in lowered), (
        "a missing-KEY row inside a READABLE file must be reported with a "
        "DIFFERENT reason than an unreadable FILE. got "
        f"{reasons!r}. {composition.diag('unified-event-store')}"
    )
    assert not any(
        "malformed" in reason or "could not parse" in reason for reason in lowered
    ), (
        "a missing-KEY row must be reported with a DIFFERENT reason than a "
        f"malformed/unparsable ledger LINE. got {reasons!r}. "
        f"{composition.diag('unified-event-store')}"
    )
    assert not any(
        "not a json object" in reason or "not an object" in reason for reason in lowered
    ), (
        "a missing-KEY row must be reported with a DIFFERENT reason than a "
        f"valid-JSON-but-non-object ROW. got {reasons!r}. "
        f"{composition.diag('unified-event-store')}"
    )
    assert not any(
        "ambiguous" in reason or "tied-max" in reason for reason in lowered
    ), (
        "a row with reduction_seq ABSENT ENTIRELY must be reported with a "
        "DIFFERENT reason than an ambiguous tied-max group -- both mention "
        f"reduction_seq but are distinct faults. got {reasons!r}. "
        f"{composition.diag('unified-event-store')}"
    )
    assert any(
        "reduction_seq" in reason
        and ("missing" in reason or "absent" in reason or "no reduction_seq" in reason)
        for reason in lowered
    ), (
        "expected a reason identifying a derived row missing its "
        f"reduction_seq key entirely, got {reasons!r}. "
        f"{composition.diag('unified-event-store')}"
    )


@then(
    "the measured and could-not-verify counts conserve the ledger's "
    "population, counting rows that share a reduction key as one fact"
)
def then_counts_conserve_the_ledger_population(
    composition: EventStoreQueryComposition,
) -> None:
    """Peer-review finding (round-3 AT review), CORRECTED (round-4, DD-17
    dispatch): `could_not_verify_count >= 1` is a THRESHOLD -- it would
    still pass an implementation that routes the bad row correctly but
    silently drops a GOOD row, or one that double-counts a fault, so a
    conservation law is the right shape of oracle. BUT the ORIGINAL law
    here (`measured + could_not_verify == raw non-blank line count`) is
    FALSE IN GENERAL and was only accidentally green on this file's prior
    fixtures: DD-7 dedup deliberately collapses N rows sharing one
    `reduction_key` into a SINGLE accounting unit (one measured winner, or
    one ambiguous-tied-max could_not_verify reason) -- never one unit per
    row. Reproduced directly: 3 rows sharing one key with a single winner
    give `measured_count == 1` against a raw population of 3, which the OLD
    law would have wrongly rejected. The corrected population is
    `expected_conservation_population()` -- every legacy/primary-new row and
    every line-level/row-shape fault counts once; every DISTINCT
    `reduction_key` among well-shaped, grouped derived rows counts once
    TOTAL, however many raw rows share it."""
    obs = composition.observable("unified-event-store")
    payload = _parse_last_json_line(obs.captured_output)
    assert payload is not None, (
        "the query must emit a JSON answer to check count conservation "
        f"against. {composition.diag('unified-event-store')}"
    )
    population = composition.expected_conservation_population()
    raw_row_count = composition.ledger_row_count()
    measured = payload.get("measured_count")
    could_not_verify = payload.get("could_not_verify_count")
    assert measured is not None and could_not_verify is not None, (
        "conservation cannot be checked without both counts present in the "
        f"answer. got payload={payload!r}. {composition.diag('unified-event-store')}"
    )
    assert measured + could_not_verify == population, (
        "measured_count + could_not_verify_count must equal the ledger's "
        "KEY-based accounting population -- a mismatch means a row/group "
        "was silently dropped from the partition, or double-counted across "
        f"its buckets. got measured_count={measured!r}, "
        f"could_not_verify_count={could_not_verify!r}, expected key-based "
        f"population={population!r} (raw non-blank ledger lines="
        f"{raw_row_count!r}, which a shared-reduction_key group "
        f"legitimately makes SMALLER than the population once collapsed). "
        f"{composition.diag('unified-event-store')}"
    )


# --- Then (DD-17 round-4: ADR-EVT-002 row-recognition contract) -----------


@then(
    "the could-not-verify count names a reason identifying a primary-new "
    "row's agent_id as the wrong type"
)
def then_primary_agent_id_wrong_type_reason(
    composition: EventStoreQueryComposition,
) -> None:
    """Primary-branch admissible `agent_id` is `None | str` (ADR-EVT-002)
    -- today ANY other type is silently counted as `measured`
    (SILENT-WRONG); DD-17 inverts this to a named `could_not_verify`
    reason."""
    obs = composition.observable("unified-event-store")
    payload = _parse_last_json_line(obs.captured_output)
    assert payload is not None, (
        "the query must emit a JSON answer even when a primary-new row has "
        f"a wrong-type agent_id. {composition.diag('unified-event-store')}"
    )
    assert payload.get("could_not_verify_count", 0) >= 1, (
        "a primary-new row whose agent_id is not None/str must raise "
        "could_not_verify_count -- it must never be silently counted as "
        f"measured. {composition.diag('unified-event-store')}"
    )
    reasons = payload.get("could_not_verify_reasons", [])
    lowered = [reason.lower() for reason in reasons]
    assert any("agent_id" in reason for reason in lowered), (
        "expected a reason identifying the primary-new row's agent_id, got "
        f"{reasons!r}. {composition.diag('unified-event-store')}"
    )


@then(
    "the could-not-verify count names a reason identifying a derived row's "
    "agent_id as the wrong type, distinguishable from a null-agent_id reason"
)
def then_derived_agent_id_wrong_type_reason(
    composition: EventStoreQueryComposition,
) -> None:
    obs = composition.observable("unified-event-store")
    payload = _parse_last_json_line(obs.captured_output)
    assert payload is not None, (
        "the query must emit a JSON answer even when a derived row has a "
        f"wrong-type agent_id. {composition.diag('unified-event-store')}"
    )
    assert payload.get("could_not_verify_count", 0) >= 1, (
        "a derived row whose agent_id is not None/str must raise "
        "could_not_verify_count -- it must never be silently counted as "
        f"measured. {composition.diag('unified-event-store')}"
    )
    reasons = payload.get("could_not_verify_reasons", [])
    lowered = [reason.lower() for reason in reasons]
    assert not any("null agent_id" in reason for reason in lowered), (
        "a WRONG-TYPE agent_id must be reported with a DIFFERENT reason "
        f"than DD-8's agent_id-present-but-NULL case. got {reasons!r}. "
        f"{composition.diag('unified-event-store')}"
    )
    assert any("agent_id" in reason for reason in lowered), (
        "expected a reason identifying the derived row's agent_id, got "
        f"{reasons!r}. {composition.diag('unified-event-store')}"
    )


@then(
    "the could-not-verify count names a reason identifying a derived row's "
    "reduction_key as inadmissible"
)
def then_derived_reduction_key_wrong_reason(
    composition: EventStoreQueryComposition,
) -> None:
    obs = composition.observable("unified-event-store")
    payload = _parse_last_json_line(obs.captured_output)
    assert payload is not None, (
        "the query must emit a JSON answer even when a derived row has an "
        f"inadmissible reduction_key. {composition.diag('unified-event-store')}"
    )
    assert payload.get("could_not_verify_count", 0) >= 1, (
        "a derived row whose reduction_key is not a non-empty str must "
        "raise could_not_verify_count -- it must never be silently counted "
        f"as measured. {composition.diag('unified-event-store')}"
    )
    reasons = payload.get("could_not_verify_reasons", [])
    lowered = [reason.lower() for reason in reasons]
    assert any("reduction_key" in reason for reason in lowered), (
        "expected a reason identifying the derived row's reduction_key, "
        f"got {reasons!r}. {composition.diag('unified-event-store')}"
    )


@then(
    "the could-not-verify count names a reason identifying a derived row's "
    "reduction_seq as the wrong type, distinguishable from an "
    "ambiguous-tied-max reason"
)
def then_derived_reduction_seq_wrong_type_reason(
    composition: EventStoreQueryComposition,
) -> None:
    """Covers BOTH the silently-accepted wrong types (bool/float/str/None/
    list/dict -- today `could_not_verify_count == 0`, the assertion below
    fails on the threshold check) AND the NaN case (today
    `could_not_verify_count == 1`, but via the self-contradictory
    "0 records tied" reason -- the assertion below fails on the
    ambiguous/tied exclusion check instead)."""
    obs = composition.observable("unified-event-store")
    payload = _parse_last_json_line(obs.captured_output)
    assert payload is not None, (
        "the query must emit a JSON answer even when a derived row has a "
        f"wrong-type reduction_seq. {composition.diag('unified-event-store')}"
    )
    assert payload.get("could_not_verify_count", 0) >= 1, (
        "a derived row whose reduction_seq is not exactly int must raise "
        "could_not_verify_count -- it must never be silently counted as "
        f"measured. {composition.diag('unified-event-store')}"
    )
    reasons = payload.get("could_not_verify_reasons", [])
    lowered = [reason.lower() for reason in reasons]
    assert not any("ambiguous" in reason or "tied" in reason for reason in lowered), (
        "a WRONG-TYPE reduction_seq (including NaN) must be reported with a "
        "type-violation reason, NEVER the ambiguous-tied-max reason -- "
        f"routing it through the tied-max path is the exact self-"
        f"contradictory bug this row exists to close. got {reasons!r}. "
        f"{composition.diag('unified-event-store')}"
    )
    assert any("reduction_seq" in reason for reason in lowered), (
        "expected a reason identifying the derived row's reduction_seq, "
        f"got {reasons!r}. {composition.diag('unified-event-store')}"
    )


@then(
    "the could-not-verify count names every one of the three violated "
    "fields from this single query, never requiring a second round to "
    "discover the rest"
)
def then_all_three_violations_named_in_one_pass(
    composition: EventStoreQueryComposition,
) -> None:
    """ADR-EVT-002's "one pass, not one-per-round" requirement: a SINGLE
    row with three simultaneous field violations must have ALL THREE named
    among the reasons this ONE query returns -- never only the first field
    checked, which would silently hide the other two until a future
    round found them (the exact round-1..4 pattern this ADR exists to
    stop)."""
    obs = composition.observable("unified-event-store")
    payload = _parse_last_json_line(obs.captured_output)
    assert payload is not None, (
        "the query must emit a JSON answer even when a derived row has "
        f"three simultaneous violations. {composition.diag('unified-event-store')}"
    )
    reasons = payload.get("could_not_verify_reasons", [])
    joined = " ".join(reasons).lower()
    missing = [
        field
        for field in ("agent_id", "reduction_key", "reduction_seq")
        if field not in joined
    ]
    assert not missing, (
        "a single row with three simultaneous field violations must name "
        f"ALL three fields from ONE query -- missing {missing!r} in "
        f"{reasons!r}. {composition.diag('unified-event-store')}"
    )


@then("no could-not-verify reason claims a tie among fewer than two records")
def then_no_reason_claims_tie_under_two_records(
    composition: EventStoreQueryComposition,
) -> None:
    """Pins the NaN self-contradiction closed: `reduction_seq=NaN` on a
    group of size ONE today emits "ambiguous tied-max ... (0 records
    tied)" -- claiming ambiguity among ZERO records, because `NaN != NaN`
    discards even the `max()` winner. DD-17 closes this by rejecting the
    row via the type contract before it can ever reach the tied-max
    grouping code; this assertion is the general invariant that would
    catch ANY future regression of the same shape, not merely this one
    fixture."""
    obs = composition.observable("unified-event-store")
    payload = _parse_last_json_line(obs.captured_output)
    assert payload is not None, (
        "the query must emit a JSON answer to check the tied-max invariant "
        f"against. {composition.diag('unified-event-store')}"
    )
    reasons = payload.get("could_not_verify_reasons", [])
    violations = [
        reason
        for reason in reasons
        if (match := re.search(r"\((\d+) records? tied\)", reason)) is not None
        and int(match.group(1)) < 2
    ]
    assert not violations, (
        "a could_not_verify reason must never claim a tie among fewer than "
        f"two records -- found self-contradictory reason(s) {violations!r} "
        f"in {reasons!r}. {composition.diag('unified-event-store')}"
    )


@then(
    "the could-not-verify count names a reason identifying an "
    "oversized-integer ledger line, distinguishable from a "
    "malformed-JSON-line reason"
)
def then_oversized_integer_line_reason(
    composition: EventStoreQueryComposition,
) -> None:
    obs = composition.observable("unified-event-store")
    payload = _parse_last_json_line(obs.captured_output)
    assert payload is not None, (
        "the query must emit a JSON answer even when one ledger line "
        f"contains an oversized integer literal. {composition.diag('unified-event-store')}"
    )
    assert payload.get("could_not_verify_count", 0) >= 1, (
        "an oversized-integer ledger line must raise could_not_verify_count "
        f"-- it must never crash the query. {composition.diag('unified-event-store')}"
    )
    reasons = payload.get("could_not_verify_reasons", [])
    lowered = [reason.lower() for reason in reasons]
    assert not any("could not parse it as json" in reason for reason in lowered), (
        "an oversized-integer LINE (syntactically valid JSON) must be "
        "reported with a DIFFERENT reason than a malformed/unparsable JSON "
        f"line. got {reasons!r}. {composition.diag('unified-event-store')}"
    )
    assert any(
        "digit" in reason or "integer" in reason or "conversion limit" in reason
        for reason in lowered
    ), (
        "expected a reason identifying an oversized-integer ledger line, "
        f"got {reasons!r}. {composition.diag('unified-event-store')}"
    )


@then(
    "the could-not-verify count names a reason identifying an "
    "excessively-nested ledger line, distinguishable from a "
    "malformed-JSON-line reason"
)
def then_excessive_nesting_line_reason(
    composition: EventStoreQueryComposition,
) -> None:
    obs = composition.observable("unified-event-store")
    payload = _parse_last_json_line(obs.captured_output)
    assert payload is not None, (
        "the query must emit a JSON answer even when one ledger line is "
        f"excessively nested. {composition.diag('unified-event-store')}"
    )
    assert payload.get("could_not_verify_count", 0) >= 1, (
        "an excessively-nested ledger line must raise could_not_verify_count "
        f"-- it must never crash the query/process. {composition.diag('unified-event-store')}"
    )
    reasons = payload.get("could_not_verify_reasons", [])
    lowered = [reason.lower() for reason in reasons]
    assert not any("could not parse it as json" in reason for reason in lowered), (
        "an excessively-nested LINE must be reported with a DIFFERENT "
        f"reason than a malformed/unparsable JSON line. got {reasons!r}. "
        f"{composition.diag('unified-event-store')}"
    )
    assert any(
        "nest" in reason or "recursion" in reason or "depth" in reason
        for reason in lowered
    ), (
        "expected a reason identifying an excessively-nested ledger line, "
        f"got {reasons!r}. {composition.diag('unified-event-store')}"
    )
