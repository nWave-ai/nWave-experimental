"""Shared version reader -- single source of truth.

Reads the project version from ``pyproject.toml`` (the canonical
source). Falls back through ``tomllib`` -> ``tomli`` -> regex.

All consumers should import from this module::

    from scripts.shared.version import get_version
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


def get_version(project_root: Path) -> str:
    """Read version from ``pyproject.toml`` in *project_root*.

    Tries ``tomllib`` (Python 3.11+), then ``tomli``, then regex.
    Returns ``"0.0.0"`` if the file is missing or unparseable.
    """
    pyproject_path = project_root / "pyproject.toml"
    if not pyproject_path.exists():
        return "0.0.0"

    # Try binary TOML parsers first
    try:
        try:
            import tomllib
        except ModuleNotFoundError:
            import tomli as tomllib  # type: ignore[no-redef]

        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        return data.get("project", {}).get("version", "0.0.0")

    except ModuleNotFoundError:
        pass
    except Exception:
        return "0.0.0"

    # Fallback: regex
    try:
        content = pyproject_path.read_text(encoding="utf-8")
        m = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
        return m.group(1) if m else "0.0.0"
    except OSError:
        return "0.0.0"
