"""Acceptance tests for HooksRegisteredCheck.

Tests enter through the check's run() driving port.
Pass path: settings.json with all required hook type keys.
Fail path: settings.json missing one or more hook keys, or file absent.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from nwave_ai.doctor.checks.hooks_registered import HooksRegisteredCheck
from nwave_ai.doctor.context import DoctorContext


if TYPE_CHECKING:
    from pathlib import Path


REQUIRED_HOOK_TYPES = [
    "PreToolUse",
    "PostToolUse",
    "SubagentStop",
    "SessionStart",
    "SubagentStart",
]


def _write_settings(context: DoctorContext, hooks: dict) -> None:
    context.claude_dir.mkdir(parents=True, exist_ok=True)
    context.settings_path.write_text(json.dumps({"hooks": hooks}))


@pytest.fixture()
def context(tmp_path: Path) -> DoctorContext:
    return DoctorContext(home_dir=tmp_path)


def test_passes_when_all_hook_types_present(context: DoctorContext) -> None:
    """run() returns passed=True when all 5 required hook type keys are present."""
    hooks = {
        hook: [{"matcher": "", "hooks": [{"type": "command", "command": "x"}]}]
        for hook in REQUIRED_HOOK_TYPES
    }
    _write_settings(context, hooks)

    check = HooksRegisteredCheck()
    result = check.run(context)
    assert result.passed is True


def test_fails_when_hook_type_missing(context: DoctorContext) -> None:
    """run() returns passed=False when a required hook type is absent."""
    hooks = {hook: [] for hook in REQUIRED_HOOK_TYPES if hook != "SubagentStop"}
    _write_settings(context, hooks)

    check = HooksRegisteredCheck()
    result = check.run(context)
    assert result.passed is False
    assert "SubagentStop" in result.message
    assert result.remediation is not None


def test_fails_gracefully_when_settings_absent(context: DoctorContext) -> None:
    """run() returns passed=False (no exception) when settings.json does not exist."""
    check = HooksRegisteredCheck()
    result = check.run(context)
    assert result.passed is False
    assert result.remediation is not None
