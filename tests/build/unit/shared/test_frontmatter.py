"""Tests for scripts/shared/frontmatter.py -- shared YAML frontmatter parser."""

import pytest

from scripts.shared.frontmatter import parse_frontmatter, parse_frontmatter_file


class TestParseFrontmatter:
    """Test parse_frontmatter() with various inputs."""

    def test_valid_frontmatter_returns_dict_and_body(self):
        content = "---\nname: test\ndescription: hello\n---\n# Body\n"
        meta, body = parse_frontmatter(content)
        assert meta == {"name": "test", "description": "hello"}
        assert body == "# Body\n"

    def test_missing_opening_delimiter_returns_none(self):
        content = "no frontmatter here\n---\nstill not\n"
        meta, body = parse_frontmatter(content)
        assert meta is None
        assert body == content

    def test_missing_closing_delimiter_returns_none(self):
        content = "---\nname: test\nno closing delimiter\n"
        meta, body = parse_frontmatter(content)
        assert meta is None
        assert body == content

    def test_file_ending_with_newline_dash_dash_dash(self):
        content = "---\nname: test\n---"
        meta, body = parse_frontmatter(content)
        assert meta == {"name": "test"}
        assert body == ""

    def test_empty_body_after_frontmatter(self):
        content = "---\nname: test\n---\n"
        meta, body = parse_frontmatter(content)
        assert meta == {"name": "test"}
        assert body == ""

    def test_malformed_yaml_returns_none(self):
        content = "---\n: :\n  - [invalid\n---\n"
        meta, body = parse_frontmatter(content)
        assert meta is None
        assert body == content

    def test_frontmatter_that_parses_as_non_dict_returns_none(self):
        content = "---\n- item1\n- item2\n---\nbody\n"
        meta, body = parse_frontmatter(content)
        assert meta is None
        assert body == content

    def test_empty_string_returns_none(self):
        meta, body = parse_frontmatter("")
        assert meta is None
        assert body == ""

    def test_triple_dash_inside_value_not_matched(self):
        """Ensures \\n---\\n delimiter is used, not find('---', 3)."""
        content = "---\nname: has---dashes\ndescription: ok\n---\nbody\n"
        meta, body = parse_frontmatter(content)
        assert meta is not None
        assert meta["name"] == "has---dashes"
        assert meta["description"] == "ok"
        assert body == "body\n"

    def test_multiline_body_preserved(self):
        content = "---\nkey: val\n---\nline1\nline2\nline3\n"
        meta, body = parse_frontmatter(content)
        assert meta == {"key": "val"}
        assert body == "line1\nline2\nline3\n"

    @pytest.mark.parametrize(
        "yaml_block,expected_value",
        [
            ("name: simple", "simple"),
            ("name: 'quoted'", "quoted"),
            ('name: "double-quoted"', "double-quoted"),
        ],
    )
    def test_yaml_value_styles(self, yaml_block, expected_value):
        content = f"---\n{yaml_block}\n---\n"
        meta, _ = parse_frontmatter(content)
        assert meta is not None
        assert meta["name"] == expected_value

    def test_complex_yaml_with_lists(self):
        content = "---\nname: agent\nskills:\n  - skill-a\n  - skill-b\n---\nbody\n"
        meta, body = parse_frontmatter(content)
        assert meta == {"name": "agent", "skills": ["skill-a", "skill-b"]}
        assert body == "body\n"


class TestParseFrontmatterFile:
    """Test parse_frontmatter_file() with filesystem access."""

    def test_reads_file_and_parses(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("---\nname: test\n---\nbody\n", encoding="utf-8")
        meta, body = parse_frontmatter_file(f)
        assert meta == {"name": "test"}
        assert body == "body\n"

    def test_missing_file_returns_none(self, tmp_path):
        meta, body = parse_frontmatter_file(tmp_path / "nonexistent.md")
        assert meta is None
        assert body == ""

    def test_file_without_frontmatter(self, tmp_path):
        f = tmp_path / "plain.md"
        f.write_text("# Just a heading\n\nSome content.\n", encoding="utf-8")
        meta, body = parse_frontmatter_file(f)
        assert meta is None
        assert body == "# Just a heading\n\nSome content.\n"

    def test_file_with_encoding_error(self, tmp_path):
        """Binary file that cannot be decoded as UTF-8."""
        f = tmp_path / "binary.md"
        f.write_bytes(b"\xff\xfe" + b"\x00" * 100)
        meta, _body = parse_frontmatter_file(f)
        # Should not raise -- returns None on error
        assert meta is None
