"""Shared helper for reading and parsing settings.json in doctor checks."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from nwave_ai.common.check_result import CheckResult


if TYPE_CHECKING:
    from pathlib import Path


def read_settings(
    settings_path: Path,
) -> tuple[dict[str, Any] | None, CheckResult | None]:
    """Read and parse settings.json, returning (data, None) on success or (None, error) on failure."""
    if not settings_path.exists():
        return None, CheckResult(
            passed=False,
            error_code="SETTINGS_MISSING",
            message="settings.json not found",
            remediation="Run `nwave-ai install` to create the Claude settings file.",
        )

    try:
        data: dict[str, Any] = json.loads(settings_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        return None, CheckResult(
            passed=False,
            error_code="SETTINGS_UNREADABLE",
            message=f"settings.json could not be parsed: {exc}",
            remediation="Inspect settings.json for syntax errors.",
        )

    return data, None
