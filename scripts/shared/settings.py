"""Shared JSON settings file loading.

Provides a single implementation for loading Claude Code ``settings.json``
files, used by DES plugin installation and uninstallation scripts.

Semantics:
  - Missing file: returns ``{}``.
  - Corrupt JSON: raises ``ValueError`` (callers that need silent fallback
    should catch explicitly).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


def load_settings(settings_file: Path) -> dict:
    """Load settings from a JSON file.

    Returns an empty dict when *settings_file* does not exist.
    Raises ``ValueError`` when the file exists but contains invalid JSON,
    ensuring corrupt configuration is never silently ignored.
    """
    if not settings_file.exists():
        return {}

    try:
        with open(settings_file, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {settings_file}: {e}") from e
