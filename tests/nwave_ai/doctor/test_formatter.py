"""Acceptance tests for formatter.render_human() and formatter.render_json().

Tests enter through render_human() and render_json() as driving ports.
Uses pre-built CheckResult fixtures — formatters are pure functions of their input.
"""

from __future__ import annotations

import json

from nwave_ai.common.check_result import CheckResult

from nwave_ai.doctor import formatter


def _make_results() -> list[CheckResult]:
    """Return 7 representative CheckResult objects (mix of pass/fail)."""
    return [
        CheckResult(
            check_name="python_version",
            passed=True,
            error_code=None,
            message="Python 3.11.0 — OK",
            remediation=None,
        ),
        CheckResult(
            check_name="des_module",
            passed=True,
            error_code=None,
            message="DES module found",
            remediation=None,
        ),
        CheckResult(
            check_name="hooks_registered",
            passed=True,
            error_code=None,
            message="All 5 hook types registered",
            remediation=None,
        ),
        CheckResult(
            check_name="hook_python_path",
            passed=True,
            error_code=None,
            message="Hook binary verified",
            remediation=None,
        ),
        CheckResult(
            check_name="shims_deployed",
            passed=True,
            error_code=None,
            message="All shims present and executable",
            remediation=None,
        ),
        CheckResult(
            check_name="path_env",
            passed=False,
            error_code="CLAUDE_BIN_NOT_IN_PATH",
            message="/home/user/.claude/bin is not in env.PATH",
            remediation="Add ~/.claude/bin to env.PATH in settings.json.",
        ),
        CheckResult(
            check_name="framework_files",
            passed=True,
            error_code=None,
            message="Framework directories populated",
            remediation=None,
        ),
    ]


def test_render_human_shows_all_7_results() -> None:
    """render_human() includes every check name in the output."""
    results = _make_results()
    output = formatter.render_human(results)

    for result in results:
        assert result.check_name in output


def test_render_human_uses_emoji_prefixes() -> None:
    """render_human() uses ✅ for pass and ⚠️ for fail."""
    results = _make_results()
    output = formatter.render_human(results)

    assert "✅" in output
    assert "⚠️" in output


def test_render_human_includes_remediation_for_failures() -> None:
    """render_human() indents remediation under failed checks."""
    results = _make_results()
    output = formatter.render_human(results)

    # The path_env check fails with a known remediation string
    assert "Add ~/.claude/bin to env.PATH" in output


def test_render_human_ends_with_summary_line() -> None:
    """render_human() ends with N/M checks passed summary."""
    results = _make_results()
    output = formatter.render_human(results)

    # 6 pass, 1 fail
    assert "6/7 checks passed" in output
    assert "1 failed" in output


def test_render_json_emits_valid_json() -> None:
    """render_json() output is parseable JSON."""
    results = _make_results()
    output = formatter.render_json(results)

    parsed = json.loads(output)
    assert isinstance(parsed, dict)


def test_render_json_has_checks_array_length_7() -> None:
    """render_json() checks array has one entry per result."""
    results = _make_results()
    output = formatter.render_json(results)

    parsed = json.loads(output)
    assert len(parsed["checks"]) == 7


def test_render_json_has_summary_dict() -> None:
    """render_json() summary dict has total/passed/failed keys."""
    results = _make_results()
    output = formatter.render_json(results)

    parsed = json.loads(output)
    summary = parsed["summary"]
    assert summary["total"] == 7
    assert summary["passed"] == 6
    assert summary["failed"] == 1
