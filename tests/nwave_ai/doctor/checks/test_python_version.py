"""Acceptance tests for PythonVersionCheck.

Tests enter through the check's run() driving port.
Pass path: interpreter >= 3.10 (true in CI).
Fail path: monkeypatch sys.version_info to simulate an old interpreter.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from nwave_ai.doctor.checks.python_version import PythonVersionCheck
from nwave_ai.doctor.context import DoctorContext


if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture()
def context(tmp_path: Path) -> DoctorContext:
    return DoctorContext(home_dir=tmp_path)


def test_passes_when_python_310_or_newer(context: DoctorContext) -> None:
    """run() returns passed=True on the current interpreter (always >= 3.10 in CI)."""
    check = PythonVersionCheck()
    result = check.run(context)
    assert result.passed is True
    assert "3." in result.message


def test_fails_when_python_older_than_310(context: DoctorContext) -> None:
    """run() returns passed=False when sys.version_info < (3, 10)."""
    old_version = (3, 9, 7, "final", 0)
    with patch.object(sys, "version_info", old_version):
        check = PythonVersionCheck()
        result = check.run(context)
    assert result.passed is False
    assert result.remediation is not None
    assert "3.10" in result.remediation
