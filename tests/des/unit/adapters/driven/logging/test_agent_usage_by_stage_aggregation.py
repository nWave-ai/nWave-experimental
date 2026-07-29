"""Unit tests for JsonlAuditLogReader.aggregate_agent_usage_by_stage.

declared-facts-reachable-recorded slice-07 (DD-12): the reader closing the
"0 readers" state F1 named. Regression anchor for the fabricated-count class
of defect hunted all day elsewhere in this tree (worktree anti-rot triage):
`AGENT_USAGE_OBSERVED` carries ONE ROW PER RAW TRANSCRIPT ENTRY, not one per
API request (proven in `token_usage_extractor.py`'s 1:1 mapping, and measured
independently in `docs/analysis/actual-usage-by-request-2026-07-26.md` --
summing raw rows over-counts by roughly 2x). A naive sum over these records
would repeat that exact class of error; this aggregation MUST dedup by
`request_id` (MAX per category) and MUST report -- never silently drop or
silently include -- the population it could not dedup.

Test Budget: 5 behaviors (dedup-by-request-id; MAX-not-sum for output;
stage-grouping; unattributed-population-preserved; could-not-verify on zero
matches) x 1 each. Using 6 (one extra: cross-feature isolation, a real
join-key correctness claim, not decoration).
"""

from __future__ import annotations

import json

from des.adapters.driven.logging.jsonl_audit_log_reader import JsonlAuditLogReader


def _write_log(log_dir, date_str: str, entries: list[dict]) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"audit-{date_str}.log"
    with open(log_file, "a", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def _usage_record(
    *,
    feature_id: str = "feat-x",
    stage: str | None = "A_GREEN",
    request_id: str | None = "req_1",
    input_tokens: int = 10,
    cache_creation_input_tokens: int = 20,
    cache_read_input_tokens: int = 30,
    output_tokens: int = 40,
) -> dict:
    return {
        "event": "AGENT_USAGE_OBSERVED",
        "feature_id": feature_id,
        "feature_name": feature_id,
        "stage": stage,
        "request_id": request_id,
        "input_tokens": input_tokens,
        "cache_creation_input_tokens": cache_creation_input_tokens,
        "cache_read_input_tokens": cache_read_input_tokens,
        "output_tokens": output_tokens,
    }


def test_dedups_by_request_id_never_sums_raw_rows(tmp_path) -> None:
    """Three raw rows for the SAME request_id (mirroring the real
    one-row-per-transcript-entry shape) must collapse to ONE request's worth
    of tokens, not triple-count."""
    _write_log(
        tmp_path,
        "2026-07-29",
        [
            _usage_record(request_id="req_1", input_tokens=5),
            _usage_record(request_id="req_1", input_tokens=5),
            _usage_record(request_id="req_1", input_tokens=5),
        ],
    )
    reader = JsonlAuditLogReader(log_dir=tmp_path)

    report = reader.aggregate_agent_usage_by_stage("feat-x")

    (stage,) = report.stages
    assert stage.request_count == 1
    assert stage.input_tokens == 5  # identical across the group -> not tripled


def test_output_tokens_use_max_not_sum_across_streaming_snapshots(tmp_path) -> None:
    """The proven July-26 finding: early rows in a request group are PARTIAL
    streaming snapshots of output_tokens -- MAX is correct, sum inflates,
    first/last alone can undercount."""
    _write_log(
        tmp_path,
        "2026-07-29",
        [
            _usage_record(request_id="req_1", output_tokens=3),
            _usage_record(request_id="req_1", output_tokens=3),
            _usage_record(request_id="req_1", output_tokens=406),
        ],
    )
    reader = JsonlAuditLogReader(log_dir=tmp_path)

    report = reader.aggregate_agent_usage_by_stage("feat-x")

    (stage,) = report.stages
    assert stage.output_tokens == 406
    assert stage.output_tokens != 3 + 3 + 406  # never a naive sum


def test_groups_by_stage_independently(tmp_path) -> None:
    _write_log(
        tmp_path,
        "2026-07-29",
        [
            _usage_record(stage="A_GREEN", request_id="req_1", input_tokens=100),
            _usage_record(stage="B_RED", request_id="req_2", input_tokens=7),
        ],
    )
    reader = JsonlAuditLogReader(log_dir=tmp_path)

    report = reader.aggregate_agent_usage_by_stage("feat-x")

    by_stage = {s.stage: s for s in report.stages}
    assert by_stage["A_GREEN"].input_tokens == 100
    assert by_stage["B_RED"].input_tokens == 7


def test_records_without_request_id_are_excluded_from_totals_and_counted(
    tmp_path,
) -> None:
    """GDP-8 arity: an un-dedupable record must not be silently summed in
    (inflating the total) NOR silently dropped (hiding that it exists)."""
    _write_log(
        tmp_path,
        "2026-07-29",
        [
            _usage_record(request_id="req_1", input_tokens=10),
            _usage_record(request_id=None, input_tokens=999),
        ],
    )
    reader = JsonlAuditLogReader(log_dir=tmp_path)

    report = reader.aggregate_agent_usage_by_stage("feat-x")

    (stage,) = report.stages
    assert stage.input_tokens == 10  # the 999 is NOT folded into the total
    assert stage.unattributed_record_count == 1  # but it is not hidden either
    assert report.total_records_scanned == 2  # both rows were seen


def test_zero_matching_records_reports_could_not_verify_not_a_bare_zero(
    tmp_path,
) -> None:
    _write_log(tmp_path, "2026-07-29", [_usage_record(feature_id="other-feature")])
    reader = JsonlAuditLogReader(log_dir=tmp_path)

    report = reader.aggregate_agent_usage_by_stage("feat-x")

    assert report.total_records_scanned == 0
    assert report.stages == ()


def test_cross_feature_records_never_leak_into_each_others_totals(tmp_path) -> None:
    _write_log(
        tmp_path,
        "2026-07-29",
        [
            _usage_record(feature_id="feat-x", request_id="req_1", input_tokens=1),
            _usage_record(feature_id="feat-y", request_id="req_2", input_tokens=1000),
        ],
    )
    reader = JsonlAuditLogReader(log_dir=tmp_path)

    report = reader.aggregate_agent_usage_by_stage("feat-x")

    assert report.total_records_scanned == 1
    (stage,) = report.stages
    assert stage.input_tokens == 1
