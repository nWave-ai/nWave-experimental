"""Regression: coverage-on-executed-path lever is runner/target-aware.

The coverage-on-executed-path lever scans a driven workspace for pytest ATs
importing the ``des`` production package -- a Python/pytest-only dogfood signal.
On a NON-Python target (sister tsunami is Rust: ATs drive the ``tsunami`` binary
via subprocess, no ``tests/test_*.py`` importing ``des``) the literal-scan found
zero hits and FALSE-FLAGGED ``CoverageOnExecutedPathFlagged`` -> ``run_contract_gate
--run-suite`` exit 2 -> ``verify-slice-commit`` E2 REFUSED -> ``SliceCommitVerified``
non-mintable on a Rust target.

The lever must mirror :func:`check_undefined_name` (the in-file canonical
target-aware pattern): on a non-pytest runner it CLEARS as NOT_APPLICABLE
carrying the loud ``health.gate.coverage-on-executed-path.not-applicable`` reason
-- NEVER a false flag. The Python/pytest theater detection is unchanged (a Python
repo whose ATs genuinely drive zero ``src/des`` lines STILL flags).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.cli import run_contract_gate
from des.cli.axis_b_levers import (
    _COVERAGE_NOT_APPLICABLE_EVENT,
    check_coverage_on_executed_path,
)


def _last_json_event(stdout: str) -> dict:
    """Parse the final single-line JSON object emitted on stdout."""
    json_lines = [line for line in stdout.splitlines() if line.strip().startswith("{")]
    return json.loads(json_lines[-1])


# --- (a) non-pytest runner -> NOT_APPLICABLE (loud reason), never a false flag


@pytest.mark.parametrize("runner", ["cargo-test", "go-test", "vitest"])
def test_non_pytest_runner_clears_not_applicable(tmp_path: Path, runner: str) -> None:
    """A non-pytest target CLEARS NOT_APPLICABLE with a loud reason, not flagged.

    The driven workspace has no ``tests/test_*.py`` importing ``des`` (the
    Rust/Go/JS shape); on the bare lever this would false-flag theater. With the
    runner threaded, the lever must instead CLEAR NOT_APPLICABLE.
    """
    lever = check_coverage_on_executed_path(tmp_path, runner=runner)

    assert lever.flagged is False, (
        f"a `{runner}` target must NOT be flagged as coverage theater -- the "
        f"pytest-only `import des` scan does not apply to it"
    )
    assert lever.structured_event == _COVERAGE_NOT_APPLICABLE_EVENT, (
        "the NOT_APPLICABLE clear must carry the loud "
        f"`{_COVERAGE_NOT_APPLICABLE_EVENT}` event (degrade-LOUD), got "
        f"{lever.structured_event!r}"
    )
    assert "NOT_APPLICABLE" in lever.remediation and runner in lever.remediation, (
        "the remediation must name the non-pytest runner and say NOT_APPLICABLE "
        f"so the failure self-explains; got {lever.remediation!r}"
    )


# --- (b) Python/pytest path is unchanged: theater still flags, real coverage clears


def test_pytest_theater_workspace_still_flags(tmp_path: Path) -> None:
    """A pytest workspace whose ATs reach zero ``des`` lines STILL flags theater."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_fixture_only.py").write_text(
        "def test_asserts_on_a_fixture():\n    assert 1 == 1\n",
        encoding="utf-8",
    )

    lever = check_coverage_on_executed_path(tmp_path, runner="pytest")

    assert lever.flagged is True, (
        "a pytest corpus whose ATs import no `des` production module is coverage "
        "theater and MUST still flag (the Python path is unchanged)"
    )
    assert lever.structured_event == "CoverageOnExecutedPathFlagged"


def test_pytest_real_coverage_workspace_clears(tmp_path: Path) -> None:
    """A pytest AT that imports a ``des`` production module clears (not flagged)."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_drives_production.py").write_text(
        "from des.cli import axis_b_levers\n\n"
        "def test_drives_the_real_port():\n    assert axis_b_levers is not None\n",
        encoding="utf-8",
    )

    lever = check_coverage_on_executed_path(tmp_path, runner="pytest")

    assert lever.flagged is False
    assert lever.structured_event == ""


def test_default_runner_preserves_python_theater_detection(tmp_path: Path) -> None:
    """The ``runner`` default is pytest: a bare call still runs theater detection."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_fixture_only.py").write_text(
        "def test_x():\n    assert True\n", encoding="utf-8"
    )

    lever = check_coverage_on_executed_path(tmp_path)  # no runner arg

    assert lever.flagged is True
    assert lever.structured_event == "CoverageOnExecutedPathFlagged"


# --- (c) run_contract_gate threads the resolved runner (the #73 resolution)


def test_gate_run_suite_on_cargo_target_clears_not_applicable(
    tmp_path: Path, capsys
) -> None:
    """``--run-suite`` on a Cargo target emits NOT_APPLICABLE + exit 0, not a flag.

    Proves ``_resolve_runner_name`` threads the resolved runner (a ``Cargo.toml``
    resolves to ``cargo-test``) into the lever, so the gate no longer false-flags
    a Rust target as coverage theater (the sister-tsunami beta-attestation blocker).
    """
    (tmp_path / "Cargo.toml").write_text(
        '[package]\nname = "demo"\nversion = "0.1.0"\n', encoding="utf-8"
    )

    exit_code = run_contract_gate.main(["--repo", str(tmp_path), "--run-suite"])

    assert exit_code == 0, "a non-pytest target must not hard-fail the gate (exit 0)"
    event = _last_json_event(capsys.readouterr().out)
    assert event["event"] == _COVERAGE_NOT_APPLICABLE_EVENT, (
        f"the gate must surface the loud NOT_APPLICABLE event; got {event!r}"
    )


def test_gate_run_suite_on_pytest_theater_target_still_flags(
    tmp_path: Path, capsys
) -> None:
    """``--run-suite`` on a pytest theater workspace still flags + exit 1 (no regression)."""
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\nversion = '0.1.0'\n", encoding="utf-8"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_fixture_only.py").write_text(
        "def test_x():\n    assert True\n", encoding="utf-8"
    )

    exit_code = run_contract_gate.main(["--repo", str(tmp_path), "--run-suite"])

    assert exit_code == 1
    event = _last_json_event(capsys.readouterr().out)
    assert event["event"] == "CoverageOnExecutedPathFlagged"
