"""Acceptance tests for HookPythonPathCheck.

Tests enter through the check's run() driving port.
Pass path (absolute): settings.json with hook command referencing an absolute binary that exists.
Pass path (bare name): settings.json with hook command referencing bare python3 + env.PATH resolves it.
Fail path: binary not resolvable (absent on disk, not in PATH).
Fail path: settings.json absent.

Regression-or-contradiction note: the original PASS test only covered absolute paths.
Hooks as installed use bare python3 resolved via env.PATH, so the old pass test encoded
the wrong behaviour.  The corrected behaviour is: bare binary names are accepted and
verified via shutil.which(name, path=settings_env_path).
"""

from __future__ import annotations

import json
import stat
from typing import TYPE_CHECKING

import pytest
from nwave_ai.doctor.checks.hook_python_path import HookPythonPathCheck
from nwave_ai.doctor.context import DoctorContext


if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture()
def context(tmp_path: Path) -> DoctorContext:
    return DoctorContext(home_dir=tmp_path)


def _write_settings(
    context: DoctorContext, command: str, env: dict | None = None
) -> None:
    context.claude_dir.mkdir(parents=True, exist_ok=True)
    hook_entry: dict = {"type": "command", "command": command}
    if env is not None:
        hook_entry["env"] = env
    settings = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Agent",
                    "hooks": [hook_entry],
                }
            ]
        }
    }
    context.settings_path.write_text(json.dumps(settings))


def _make_executable(path: Path) -> None:
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_passes_when_absolute_python_binary_exists(
    context: DoctorContext, tmp_path: Path
) -> None:
    """run() returns passed=True when hook command references an absolute python binary that exists."""
    bin_dir = tmp_path / ".claude" / "bin"
    bin_dir.mkdir(parents=True)
    python_bin = bin_dir / "python3"
    python_bin.write_text('#!/bin/sh\nexec python3 "$@"\n')
    _make_executable(python_bin)

    command = f"PYTHONPATH={tmp_path}/.claude/lib/python {python_bin} -m des"
    _write_settings(context, command)

    check = HookPythonPathCheck()
    result = check.run(context)

    assert result.passed is True


def test_passes_when_bare_python3_resolves_via_env_path(
    context: DoctorContext, tmp_path: Path
) -> None:
    """run() returns passed=True when hook uses bare 'python3' resolved via settings env PATH."""
    # Stage a fake python3 binary in a temp bin dir
    fake_bin_dir = tmp_path / "fake_bin"
    fake_bin_dir.mkdir()
    fake_python = fake_bin_dir / "python3"
    fake_python.write_text('#!/bin/sh\nexec python3 "$@"\n')
    _make_executable(fake_python)

    command = "PYTHONPATH=$HOME/.claude/lib/python python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter pre-task"
    _write_settings(context, command, env={"PATH": str(fake_bin_dir)})

    check = HookPythonPathCheck()
    result = check.run(context)

    assert result.passed is True


# ---------------------------------------------------------------------------
# Failure paths — genuine breakage must still be detected
# ---------------------------------------------------------------------------


def test_fails_when_absolute_python_binary_absent(
    context: DoctorContext, tmp_path: Path
) -> None:
    """run() returns passed=False when the absolute python binary path does not exist."""
    command = f"PYTHONPATH={tmp_path}/.claude/lib/python {tmp_path}/.claude/bin/python3 -m des"
    _write_settings(context, command)

    check = HookPythonPathCheck()
    result = check.run(context)

    assert result.passed is False
    assert result.remediation is not None


def test_fails_when_bare_python3_not_in_env_path(
    context: DoctorContext, tmp_path: Path
) -> None:
    """run() returns passed=False when bare python3 cannot be found in the env PATH."""
    empty_dir = tmp_path / "empty_bin"
    empty_dir.mkdir()

    command = "PYTHONPATH=$HOME/.claude/lib/python python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter pre-task"
    _write_settings(context, command, env={"PATH": str(empty_dir)})

    check = HookPythonPathCheck()
    result = check.run(context)

    assert result.passed is False
    assert result.remediation is not None


def test_fails_gracefully_when_settings_absent(context: DoctorContext) -> None:
    """run() returns passed=False (no exception) when settings.json does not exist."""
    check = HookPythonPathCheck()
    result = check.run(context)

    assert result.passed is False
    assert result.remediation is not None
