"""CLI integration tests for `nwave-ai doctor` subcommand.

Tests enter through the CLI main() function (driving port) and assert on
exit codes and stdout output — observable behavioral outcomes only.

Step 01-04: register doctor subcommand in nwave_ai/cli.py.
"""

from __future__ import annotations

import json
from io import StringIO
from unittest.mock import patch

from nwave_ai.cli import main


def _invoke(args: list[str]) -> tuple[int, str]:
    """Invoke CLI main() with the given sys.argv arguments.

    Returns:
        Tuple of (exit_code, stdout_output).
    """
    stdout_capture = StringIO()
    with patch("sys.argv", ["nwave-ai", *args]):
        with patch("sys.stdout", stdout_capture):
            try:
                exit_code = main()
            except SystemExit as exc:
                exit_code = int(exc.code) if exc.code is not None else 0
    return exit_code, stdout_capture.getvalue()


def test_doctor_command_runs_and_returns_0_or_1() -> None:
    """nwave-ai doctor runs without error (exit 0 all pass, 1 any fail, never 2)."""
    exit_code, stdout = _invoke(["doctor"])
    # Must be 0 (all pass) or 1 (some fail) — never 2 (usage error)
    assert exit_code in (0, 1), (
        f"Unexpected exit code {exit_code!r}, stdout: {stdout!r}"
    )
    # Human output must contain at least some text
    assert stdout.strip(), "Expected non-empty human-readable output"


def test_doctor_json_flag_emits_parseable_json_with_checks_and_summary() -> None:
    """nwave-ai doctor --json emits parseable JSON with 'checks' array and 'summary' dict."""
    exit_code, stdout = _invoke(["doctor", "--json"])
    assert exit_code in (0, 1), f"Unexpected exit code {exit_code!r}"

    data = json.loads(stdout)
    assert "checks" in data, f"Missing 'checks' key in JSON output: {data}"
    assert "summary" in data, f"Missing 'summary' key in JSON output: {data}"
    assert isinstance(data["checks"], list), "'checks' must be a list"
    assert isinstance(data["summary"], dict), "'summary' must be a dict"


def test_doctor_fix_flag_exits_2_with_not_implemented_message() -> None:
    """nwave-ai doctor --fix exits 2 with 'not yet implemented' message."""
    exit_code, stdout = _invoke(["doctor", "--fix"])
    assert exit_code == 2, f"Expected exit code 2, got {exit_code!r}"
    assert "not yet implemented" in stdout.lower(), (
        f"Expected 'not yet implemented' in output, got: {stdout!r}"
    )


def test_doctor_help_shows_flags() -> None:
    """nwave-ai doctor --help shows available flags without error exit."""
    exit_code, stdout = _invoke(["doctor", "--help"])
    # --help typically exits 0
    assert exit_code == 0, f"Unexpected exit code {exit_code!r}"
    assert "--json" in stdout or "json" in stdout.lower(), (
        f"Expected --json flag in help output: {stdout!r}"
    )
