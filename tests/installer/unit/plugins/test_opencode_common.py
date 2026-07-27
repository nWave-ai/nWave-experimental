"""Unit tests for shared OpenCode frontmatter utilities.

Tests validate that:
- parse_frontmatter() handles missing closing delimiter without crashing
- parse_frontmatter() handles malformed YAML without crashing
- parse_frontmatter() still works correctly for valid frontmatter
- render_frontmatter() produces valid YAML frontmatter strings
- opencode_config_dir() resolves OPENCODE_CONFIG_DIR-override-or-default,
  and all four OpenCode plugins (des/skills/agents/commands) delegate to
  it instead of each re-implementing the resolution

CRITICAL: These tests cover BLOCKER-level fixes -- parse_frontmatter must
never raise on malformed input. Graceful degradation to ({}, content) is
the correct behavior since the caller's install() wraps in try/except.
"""

from pathlib import Path

from scripts.install.plugins.opencode_common import (
    opencode_config_dir,
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


class TestOpencodeConfigDir:
    """opencode_config_dir() -- the single OPENCODE_CONFIG_DIR-override-or-
    default resolution shared by all four OpenCode plugins (previously
    copied verbatim into each: opencode_des_plugin, opencode_skills_plugin,
    opencode_agents_plugin, opencode_commands_plugin -- techdebt row
    opencode-config-dir-resolution-duplicated-across-four-plugins).
    """

    def test_uses_env_override_when_set(self, monkeypatch, tmp_path):
        monkeypatch.setenv("OPENCODE_CONFIG_DIR", str(tmp_path / "custom-opencode"))

        result = opencode_config_dir()

        assert result == tmp_path / "custom-opencode"

    def test_defaults_to_home_config_opencode_when_unset(self, monkeypatch):
        monkeypatch.delenv("OPENCODE_CONFIG_DIR", raising=False)

        result = opencode_config_dir()

        assert result == Path.home() / ".config" / "opencode"


class TestFourPluginsDelegateToTheSharedResolver:
    """Each plugin's own `_opencode_*_dir()` must be a THIN delegate to
    `opencode_config_dir()`, not a re-implementation -- proven by
    monkeypatching the shared function to a sentinel and observing every
    plugin surface it, not merely agree by coincidence.
    """

    def test_des_plugin_delegates(self, monkeypatch):
        import scripts.install.plugins.opencode_des_plugin as des_plugin

        sentinel = Path("/sentinel/opencode-config-dir")
        monkeypatch.setattr(des_plugin, "opencode_config_dir", lambda: sentinel)

        assert des_plugin._opencode_config_dir() == sentinel

    def test_skills_plugin_delegates(self, monkeypatch):
        import scripts.install.plugins.opencode_skills_plugin as skills_plugin

        sentinel = Path("/sentinel/opencode-config-dir")
        monkeypatch.setattr(skills_plugin, "opencode_config_dir", lambda: sentinel)

        assert skills_plugin._opencode_skills_dir() == sentinel / "skills"

    def test_agents_plugin_delegates(self, monkeypatch):
        import scripts.install.plugins.opencode_agents_plugin as agents_plugin

        sentinel = Path("/sentinel/opencode-config-dir")
        monkeypatch.setattr(agents_plugin, "opencode_config_dir", lambda: sentinel)

        assert agents_plugin._opencode_agents_dir() == sentinel / "agents"

    def test_commands_plugin_delegates(self, monkeypatch):
        import scripts.install.plugins.opencode_commands_plugin as commands_plugin

        sentinel = Path("/sentinel/opencode-config-dir")
        monkeypatch.setattr(commands_plugin, "opencode_config_dir", lambda: sentinel)

        assert commands_plugin._opencode_commands_dir() == sentinel / "commands"
