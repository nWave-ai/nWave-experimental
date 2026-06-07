"""
Shared fixtures for residuality stressor matrix tests.

Stressor matrix re-test (US-14) — converts all 19 stressors from the
residuality Layer-1 analysis into automated test fixtures.

Baseline (v1.0): 6 strict / 7 partial / 6 fail
Target (v1.1):  >=9 strict / <=6 fail

Reference: docs/feature/unified-feature-delta/feature-delta.md §US-14
"""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

import pytest


if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def write_feature_delta(tmp_path: Path):
    """Write a feature-delta.md file under a temp directory and return its path."""

    def _write(content: str) -> Path:
        path = tmp_path / "feature-delta.md"
        path.write_text(content, encoding="utf-8")
        return path

    return _write


@pytest.fixture
def run_validator():
    """
    Run the validator CLI as a subprocess and return (exit_code, stdout, stderr).

    Uses the project Python to invoke `nwave_ai.feature_delta.cli` directly.
    Driving port: validate_feature_delta_command() through the CLI dispatcher.
    """

    def _run(path: Path, extra_args: list[str] | None = None) -> tuple[int, str, str]:
        argv = [
            sys.executable,
            "-m",
            "nwave_ai.cli",
            "validate-feature-delta",
            str(path),
        ]
        if extra_args:
            argv.extend(extra_args)
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return result.returncode, result.stdout, result.stderr

    return _run
