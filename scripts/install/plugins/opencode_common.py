"""Shared frontmatter utilities for OpenCode installer plugins.

Provides pure functions for parsing and rendering YAML frontmatter,
used by both opencode_agents_plugin and opencode_commands_plugin.

These functions handle malformed input gracefully by returning empty
dicts rather than raising exceptions -- the caller's install() method
wraps everything in try/except for higher-level error reporting.
"""

import yaml


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Split YAML frontmatter from body content.

    Expects content in the form:
        ---
        key: value
        ---

        Body content here.

    Handles gracefully:
    - Missing opening delimiter: returns ({}, content)
    - Missing closing delimiter: returns ({}, content)
    - Malformed YAML: returns ({}, content)

    Args:
        content: Full file content with YAML frontmatter

    Returns:
        Tuple of (parsed frontmatter dict, body string including leading newline)
    """
    if not content.startswith("---"):
        return {}, content

    end_index = content.find("---", 3)
    if end_index == -1:
        return {}, content

    frontmatter_text = content[3:end_index].strip()
    body = content[end_index + 3 :]

    try:
        frontmatter = yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError:
        return {}, content

    return frontmatter, body


def render_frontmatter(frontmatter: dict) -> str:
    """Serialize a frontmatter dict back to YAML frontmatter string.

    Uses block style for nested mappings (not flow style) because
    OpenCode's Zod parser expects a record format.

    Args:
        frontmatter: Transformed frontmatter dict

    Returns:
        String in "---\\nkey: value\\n---" format
    """
    yaml_text = yaml.dump(
        frontmatter,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )
    return f"---\n{yaml_text}---"
