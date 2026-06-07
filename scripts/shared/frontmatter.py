"""Shared YAML frontmatter parser -- single source of truth.

Replaces 13 independent frontmatter parsers across the codebase.
Uses ``\\n---\\n`` delimiter (not ``text.find("---", 3)`` which
matches triple-dash inside YAML values).

All consumers should import from this module::

    from scripts.shared.frontmatter import parse_frontmatter, parse_frontmatter_file
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


def parse_frontmatter(content: str) -> tuple[dict | None, str]:
    """Parse YAML frontmatter from a string.

    Expects content starting with ``---\\n``, followed by YAML, followed
    by ``\\n---\\n`` (or ``\\n---`` at end of file).

    Returns ``(metadata_dict, body)`` on success, or ``(None, content)``
    if no valid frontmatter is found or parsing fails. Never raises.
    """
    if not content.startswith("---\n"):
        return None, content

    rest = content[4:]

    # Try normal delimiter first: \n---\n
    idx = rest.find("\n---\n")
    if idx != -1:
        yaml_block = rest[:idx]
        body = rest[idx + 5 :]
    elif rest.endswith("\n---"):
        # File ends with \n--- (no trailing newline after delimiter)
        yaml_block = rest[: -len("\n---")]
        body = ""
    else:
        return None, content

    try:
        import yaml

        parsed = yaml.safe_load(yaml_block)
    except Exception:
        return None, content

    if not isinstance(parsed, dict):
        return None, content

    return parsed, body


def parse_frontmatter_file(path: Path) -> tuple[dict | None, str]:
    """Read a file and parse its YAML frontmatter.

    Returns ``(metadata_dict, body)`` on success, or ``(None, "")``
    on ``OSError`` / encoding errors. Never raises.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None, ""

    return parse_frontmatter(content)
