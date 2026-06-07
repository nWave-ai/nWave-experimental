"""Acceptance tests for PathEnvCheck.

Tests enter through the check's run() driving port.
Pass path: settings.json env.PATH contains $HOME/.claude/bin equivalent.
Fail path: env.PATH absent or does not contain the bin directory.
Fail path: settings.json absent.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from nwave_ai.doctor.checks.path_env import PathEnvCheck
from nwave_ai.doctor.context import DoctorContext


if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture()
def context(tmp_path: Path) -> DoctorContext:
    return DoctorContext(home_dir=tmp_path)


def _write_settings_with_path(context: DoctorContext, path_value: str) -> None:
    context.claude_dir.mkdir(parents=True, exist_ok=True)
    context.settings_path.write_text(json.dumps({"env": {"PATH": path_value}}))


def test_passes_when_claude_bin_in_path(context: DoctorContext) -> None:
    """run() returns passed=True when claude_dir/bin appears in env.PATH."""
    claude_bin = str(context.claude_dir / "bin")
    _write_settings_with_path(context, f"/usr/bin:{claude_bin}:/usr/local/bin")

    check = PathEnvCheck()
    result = check.run(context)
    assert result.passed is True


def test_fails_when_claude_bin_not_in_path(context: DoctorContext) -> None:
    """run() returns passed=False when claude_dir/bin is absent from env.PATH."""
    _write_settings_with_path(context, "/usr/bin:/usr/local/bin")

    check = PathEnvCheck()
    result = check.run(context)
    assert result.passed is False
    assert result.remediation is not None


def test_fails_when_env_section_absent(context: DoctorContext) -> None:
    """run() returns passed=False when settings.json has no env section."""
    context.claude_dir.mkdir(parents=True, exist_ok=True)
    context.settings_path.write_text(json.dumps({"hooks": {}}))

    check = PathEnvCheck()
    result = check.run(context)
    assert result.passed is False
    assert result.remediation is not None


def test_fails_gracefully_when_settings_absent(context: DoctorContext) -> None:
    """run() returns passed=False (no exception) when settings.json does not exist."""
    check = PathEnvCheck()
    result = check.run(context)
    assert result.passed is False
    assert result.remediation is not None
