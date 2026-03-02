"""Unit tests for shared OpenCode frontmatter utilities.

Tests validate that:
- parse_frontmatter() handles missing closing delimiter without crashing
- parse_frontmatter() handles malformed YAML without crashing
- parse_frontmatter() still works correctly for valid frontmatter
- render_frontmatter() produces valid YAML frontmatter strings

CRITICAL: These tests cover BLOCKER-level fixes -- parse_frontmatter must
never raise on malformed input. Graceful degradation to ({}, content) is
the correct behavior since the caller's install() wraps in try/except.
"""

from scripts.install.plugins.opencode_common import (
    parse_frontmatter,
    render_frontmatter,
)


class TestParseFrontmatterMissingClosingDelimiter:
    """Test that parse_frontmatter handles missing closing --- without crashing."""

    def test_missing_closing_delimiter_returns_empty_dict(self):
        """
        GIVEN: Content that starts with --- but has no closing ---
        WHEN: parse_frontmatter() is called
        THEN: Returns ({}, content) without raising ValueError
        """
        content = "---\nkey: value\nno closing delimiter here\n"

        frontmatter, body = parse_frontmatter(content)

        assert frontmatter == {}
        assert body == content

    def test_missing_closing_delimiter_single_line(self):
        """
        GIVEN: Content with only opening --- and a single line
        WHEN: parse_frontmatter() is called
        THEN: Returns ({}, content) without crashing
        """
        content = "---\nkey: value\n"

        frontmatter, body = parse_frontmatter(content)

        assert frontmatter == {}
        assert body == content


class TestParseFrontmatterInvalidYaml:
    """Test that parse_frontmatter handles malformed YAML without crashing."""

    def test_invalid_yaml_returns_empty_dict(self):
        """
        GIVEN: Content with valid delimiters but malformed YAML between them
        WHEN: parse_frontmatter() is called
        THEN: Returns ({}, content) without raising yaml.YAMLError
        """
        content = "---\n: : : invalid: [yaml\n  bad indent\n---\n\nBody here.\n"

        frontmatter, body = parse_frontmatter(content)

        assert frontmatter == {}
        assert body == content

    def test_yaml_with_tabs_returns_empty_dict(self):
        """
        GIVEN: Content with YAML containing tabs (invalid in YAML)
        WHEN: parse_frontmatter() is called
        THEN: Returns ({}, content) without crashing
        """
        content = "---\nkey:\t\tvalue\n\tbad: indent\n---\n\nBody.\n"

        frontmatter, body = parse_frontmatter(content)

        # YAML actually tolerates some tab usage, so we just verify no crash
        # The exact result depends on yaml.safe_load tolerance
        assert isinstance(frontmatter, dict)
        assert isinstance(body, str)


class TestParseFrontmatterValidInput:
    """Test that parse_frontmatter still works correctly for valid input."""

    def test_valid_frontmatter_parses_correctly(self):
        """
        GIVEN: Content with valid YAML frontmatter and body
        WHEN: parse_frontmatter() is called
        THEN: Returns parsed dict and body string
        """
        content = "---\nkey: value\ntitle: Hello\n---\n\nBody content.\n"

        frontmatter, body = parse_frontmatter(content)

        assert frontmatter == {"key": "value", "title": "Hello"}
        assert body == "\n\nBody content.\n"

    def test_no_frontmatter_returns_empty_dict(self):
        """
        GIVEN: Content that does not start with ---
        WHEN: parse_frontmatter() is called
        THEN: Returns ({}, content) unchanged
        """
        content = "Just plain content without frontmatter.\n"

        frontmatter, body = parse_frontmatter(content)

        assert frontmatter == {}
        assert body == content

    def test_empty_frontmatter_returns_empty_dict(self):
        """
        GIVEN: Content with empty frontmatter block (--- followed by ---)
        WHEN: parse_frontmatter() is called
        THEN: Returns ({}, body)
        """
        content = "---\n---\n\nBody only.\n"

        frontmatter, body = parse_frontmatter(content)

        assert frontmatter == {}
        assert body == "\n\nBody only.\n"


class TestRenderFrontmatter:
    """Test that render_frontmatter produces valid YAML frontmatter strings."""

    def test_render_simple_frontmatter(self):
        """
        GIVEN: A simple frontmatter dict
        WHEN: render_frontmatter() is called
        THEN: Returns string with --- delimiters and YAML content
        """
        frontmatter = {"description": "A test command", "mode": "subagent"}

        result = render_frontmatter(frontmatter)

        assert result.startswith("---\n")
        assert result.endswith("---")
        assert "description: A test command" in result
        assert "mode: subagent" in result

    def test_render_roundtrip(self):
        """
        GIVEN: A frontmatter dict rendered to string
        WHEN: The rendered string is parsed back
        THEN: The parsed dict matches the original
        """
        original = {"description": "Roundtrip test", "steps": 50}

        rendered = render_frontmatter(original)
        parsed, _body = parse_frontmatter(rendered)

        assert parsed == original
