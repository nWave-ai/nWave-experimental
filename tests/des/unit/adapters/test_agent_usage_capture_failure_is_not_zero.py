"""A capture failure must never read as a genuine zero.

The minimum prospective capture specification requires that "capture failures
are distinguishable from genuine zero eligible events". The K3 calibration probe
found that requirement broken: `aggregate_agent_usage_by_stage` skipped an
unreadable log file with a bare `continue` and an undecodable line with another,
so three materially different corpora produced byte-identical reports —

* a corpus that genuinely held no matching event;
* a corpus whose ONE log file held three real events and could not be read;
* a corpus whose three records were corrupt.

All three returned zero stages, zero requests, zero tokens, zero unattributed.
A run whose logs were partly unreadable therefore reported a SMALLER, PLAUSIBLE
number with no signal that anything was missing — the silent-wrong GDP-6 forbids,
on the very instrument the mission's token axis is measured with.

These tests pin the discrimination itself, not the counter values, so the reader
stays free to report the loss differently as long as it still reports it.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

import pytest

from des.adapters.driven.logging.jsonl_audit_log_reader import JsonlAuditLogReader


_FEATURE = "k3-writer-failure-probe"


def _usage_record(request_id: str, output_tokens: int) -> str:
    return json.dumps(
        {
            "event": "AGENT_USAGE_OBSERVED",
            "feature_id": _FEATURE,
            "stage": "DELIVER",
            "request_id": request_id,
            "input_tokens": 10,
            "cache_creation_input_tokens": 20,
            "cache_read_input_tokens": 30,
            "output_tokens": output_tokens,
        }
    )


def _report(log_dir: Path):
    return JsonlAuditLogReader(log_dir).aggregate_agent_usage_by_stage(_FEATURE)


@pytest.fixture
def genuinely_empty(tmp_path: Path) -> Path:
    """A log that exists and honestly holds no event for this feature."""
    d = tmp_path / "genuinely-empty"
    d.mkdir()
    (d / "audit-2026-08-06.log").write_text('{"event": "SOMETHING_ELSE"}\n')
    return d


@pytest.fixture
def unreadable_file(tmp_path: Path) -> Path:
    """A log holding three REAL events that the reader cannot open."""
    d = tmp_path / "unreadable"
    d.mkdir()
    log = d / "audit-2026-08-06.log"
    log.write_text(
        "\n".join(_usage_record(f"req-{i}", 100 + i) for i in range(3)) + "\n"
    )
    log.chmod(0o000)
    yield d
    log.chmod(0o644)


@pytest.fixture
def corrupt_records(tmp_path: Path) -> Path:
    """A readable log whose three records are not valid JSON."""
    d = tmp_path / "corrupt"
    d.mkdir()
    (d / "audit-2026-08-06.log").write_text("{not json at all\n" * 3)
    return d


@pytest.mark.skipif(
    os.geteuid() == 0,
    reason="root bypasses the permission bit, so an unreadable file cannot be staged",
)
def test_an_unreadable_log_is_not_reported_as_an_empty_one(
    genuinely_empty: Path, unreadable_file: Path
) -> None:
    empty = _report(genuinely_empty)
    lost = _report(unreadable_file)

    assert asdict(lost) != asdict(empty), (
        "a log file holding three real events that could not be read produced "
        "the SAME report as a corpus that genuinely held none. Every token "
        "total below it is then a lower bound presented as a measurement."
    )
    assert lost.unreadable_file_count == 1
    assert empty.capture_is_complete is True
    assert lost.capture_is_complete is False


def test_corrupt_records_are_not_reported_as_absent_ones(
    genuinely_empty: Path, corrupt_records: Path
) -> None:
    empty = _report(genuinely_empty)
    lost = _report(corrupt_records)

    assert asdict(lost) != asdict(empty), (
        "three corrupt records produced the SAME report as a corpus that held "
        "no record at all; a writer defect is invisible to every consumer."
    )
    assert lost.undecodable_line_count == 3
    assert lost.capture_is_complete is False


def test_a_clean_corpus_still_reports_complete_capture(tmp_path: Path) -> None:
    """The discrimination must not fire on a healthy corpus.

    Without this, making the two cases above pass is trivially satisfiable by a
    reader that always claims loss — the counter-shaped version of the vacuous
    pass this file exists to prevent.
    """
    d = tmp_path / "clean"
    d.mkdir()
    (d / "audit-2026-08-06.log").write_text(
        "\n".join(_usage_record(f"req-{i}", 100 + i) for i in range(3)) + "\n"
    )

    report = _report(d)

    assert report.capture_is_complete is True
    assert report.unreadable_file_count == 0
    assert report.undecodable_line_count == 0
    assert sum(s.request_count for s in report.stages) == 3
