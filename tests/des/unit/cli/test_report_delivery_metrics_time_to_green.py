"""Unit tests for report_delivery_metrics.time_to_green_report.

declared-facts-reachable-recorded slice-07 (DD-12): joins RedObserved x
SliceCommitVerified on slice_id, replacing the git-history join the source
design named as a git-free-constraint violation (AD-21) -- this is a pure
function over already-read ledger records, no git, no filesystem.

Three states, not a bare duration (GDP-8 arity) -- GREEN (both events,
duration computed), IN_PROGRESS (red only, still open), UNATTRIBUTED (green
with no matching red -- e.g. pre-slice-06 data). UNATTRIBUTED must never be
silently dropped or folded into GREEN with a fabricated/absent duration.

Test Budget: 4 states/behaviors (GREEN duration; IN_PROGRESS; UNATTRIBUTED;
first-red-to-first-green when multiple of either exist) x 1 each.
"""

from __future__ import annotations

import pytest

from des.cli.report_delivery_metrics import time_to_green_report


def _red(slice_id: str, ts: str) -> dict:
    return {"event": "RedObserved", "slice_id": slice_id, "timestamp": ts}


def _green(slice_id: str, ts: str) -> dict:
    return {"event": "SliceCommitVerified", "slice_id": slice_id, "timestamp": ts}


def test_slice_with_both_events_reports_green_with_computed_duration() -> None:
    records = [
        _red("slice-01", "2026-07-28T18:17:57.229028Z"),
        _green("slice-01", "2026-07-28T18:56:45.580748Z"),
    ]

    (result,) = time_to_green_report(records)

    assert result.status == "GREEN"
    assert result.duration_seconds == pytest.approx(2328.35172)


def test_slice_with_only_red_is_in_progress_no_duration() -> None:
    records = [_red("slice-02", "2026-07-29T10:00:00Z")]

    (result,) = time_to_green_report(records)

    assert result.status == "IN_PROGRESS"
    assert result.duration_seconds is None
    assert result.green_verified_at is None


def test_slice_with_only_green_is_unattributed_never_dropped() -> None:
    """A SliceCommitVerified with no matching RedObserved (e.g. pre-slice-06
    data, or the flags were omitted) must surface as its own state, never
    silently dropped from the result and never folded into GREEN."""
    records = [_green("slice-03", "2026-07-29T10:00:00Z")]

    (result,) = time_to_green_report(records)

    assert result.status == "UNATTRIBUTED"
    assert result.duration_seconds is None
    assert result.red_observed_at is None


def test_uses_first_red_and_first_green_at_or_after_it() -> None:
    """A re-verified slice (two RedObserved, two SliceCommitVerified) reports
    time-to-FIRST-green, not the latest pair."""
    records = [
        _red("slice-01", "2026-07-28T10:00:00Z"),
        _green("slice-01", "2026-07-28T10:05:00Z"),
        _red("slice-01", "2026-07-28T11:00:00Z"),  # re-opened
        _green("slice-01", "2026-07-28T11:10:00Z"),  # re-verified
    ]

    (result,) = time_to_green_report(records)

    assert result.red_observed_at == "2026-07-28T10:00:00Z"
    assert result.green_verified_at == "2026-07-28T10:05:00Z"
    assert result.duration_seconds == 300.0
