"""Tests for scripts/reports/docs_link_report.py (the weekly Slack reporter).

Covers the pure formatter only — no network, no Slack. Excluded from releases
alongside the reporter it covers.
"""

from __future__ import annotations

from scripts.check_docs_links import Finding, Severity
from scripts.reports.docs_link_report import MAX_LISTED, format_report, run_check


def _f(sev: Severity, n: int = 1) -> Finding:
    return Finding(sev, f"docs/a{n}.md", n, f"http://x/{n}", "msg")


def test_clean_report_is_healthy():
    out = format_report([])
    assert "all links healthy" in out
    assert "error" not in out.lower()


def test_clean_report_includes_run_url():
    out = format_report([], run_url="https://ci/run/1")
    assert "https://ci/run/1" in out


def test_report_counts_errors_and_warnings():
    findings = [_f(Severity.ERROR, 1), _f(Severity.WARNING, 2), _f(Severity.WARNING, 3)]
    out = format_report(findings)
    assert "1 error(s), 2 warning(s)" in out
    assert ":rotating_light:" in out  # errors present


def test_report_warning_only_uses_warning_icon():
    out = format_report([_f(Severity.WARNING)])
    assert ":warning:" in out
    assert ":rotating_light:" not in out


def test_report_truncates_long_lists():
    findings = [_f(Severity.ERROR, i) for i in range(MAX_LISTED + 5)]
    out = format_report(findings)
    assert f"and {5} more" in out


def test_run_check_constructs_options_and_runs(tmp_path, monkeypatch):
    # Regression: run_check must build Options with valid kwargs and not crash.
    # Force the network canary offline so the test stays hermetic.
    monkeypatch.setattr(
        "scripts.reports.docs_link_report._network_reachable", lambda _t: False
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "target.md").write_text("# t", encoding="utf-8")
    (tmp_path / "docs" / "a.md").write_text("[t](target.md)\n", encoding="utf-8")
    findings = run_check(tmp_path)
    assert findings == []
