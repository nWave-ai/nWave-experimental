"""Tests for scripts/release/read_toml_field.py

Extracts inline TOML field-reading logic from release-prod.yml into a testable
standalone script.  Tests run the script via subprocess to validate the
real CLI contract.

BDD scenario mapping:
  - release-prod.yml "Save current nwave-ai version" (P7: project.version)
  - release-prod.yml "Calculate nwave-ai version" (P8: tool.nwave.public_version)
  - Replaces fragile line-parsing inline Python blocks with proper TOML parsing
"""

from __future__ import annotations

import subprocess
import sys


def _run_read_toml(args: list[str]) -> subprocess.CompletedProcess:
    """Run read_toml_field.py as a subprocess and return the result."""
    return subprocess.run(
        [sys.executable, "-m", "scripts.release.read_toml_field", *args],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Reading project version (P7 replacement)
# ---------------------------------------------------------------------------


class TestReadProjectVersion:
    """Reading version from the [project] table."""

    def test_reads_project_version(self, tmp_path):
        """Given a pyproject.toml with [project] version = '1.2.3',
        when reading --key project.version,
        then stdout is '1.2.3'."""
        toml_content = '[project]\nname = "test"\nversion = "1.2.3"\n'
        (tmp_path / "pyproject.toml").write_text(toml_content)

        result = _run_read_toml(
            [
                "--file",
                str(tmp_path / "pyproject.toml"),
                "--key",
                "project.version",
            ]
        )

        assert result.returncode == 0
        assert result.stdout.strip() == "1.2.3"

    def test_reads_nested_tool_field(self, tmp_path):
        """Given a pyproject.toml with [tool.nwave] public_version = '1.1.0',
        when reading --key tool.nwave.public_version,
        then stdout is '1.1.0'."""
        toml_content = '[project]\nname = "test"\nversion = "1.2.3"\n\n[tool.nwave]\npublic_version = "1.1.0"\n'
        (tmp_path / "pyproject.toml").write_text(toml_content)

        result = _run_read_toml(
            [
                "--file",
                str(tmp_path / "pyproject.toml"),
                "--key",
                "tool.nwave.public_version",
            ]
        )

        assert result.returncode == 0
        assert result.stdout.strip() == "1.1.0"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Error paths for missing files and keys."""

    def test_missing_file_exits_with_error(self, tmp_path):
        """Given --file points to nonexistent file,
        then exit code is 1."""
        result = _run_read_toml(
            [
                "--file",
                str(tmp_path / "nonexistent.toml"),
                "--key",
                "project.version",
            ]
        )

        assert result.returncode == 1
        assert result.stderr.strip() != ""

    def test_missing_key_exits_with_error(self, tmp_path):
        """Given --key points to nonexistent field,
        then exit code is 1."""
        toml_content = '[project]\nname = "test"\nversion = "1.2.3"\n'
        (tmp_path / "pyproject.toml").write_text(toml_content)

        result = _run_read_toml(
            [
                "--file",
                str(tmp_path / "pyproject.toml"),
                "--key",
                "project.nonexistent",
            ]
        )

        assert result.returncode == 1
        assert result.stderr.strip() != ""

    def test_partial_key_path_exits_with_error(self, tmp_path):
        """Given --key 'project.nonexistent.deep',
        then exit code is 1."""
        toml_content = '[project]\nname = "test"\nversion = "1.2.3"\n'
        (tmp_path / "pyproject.toml").write_text(toml_content)

        result = _run_read_toml(
            [
                "--file",
                str(tmp_path / "pyproject.toml"),
                "--key",
                "project.nonexistent.deep",
            ]
        )

        assert result.returncode == 1
        assert result.stderr.strip() != ""


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases for TOML field reading."""

    def test_reads_integer_field(self, tmp_path):
        """Given a TOML with count = 42,
        when reading that field,
        then stdout is '42'."""
        toml_content = "count = 42\n"
        (tmp_path / "data.toml").write_text(toml_content)

        result = _run_read_toml(
            [
                "--file",
                str(tmp_path / "data.toml"),
                "--key",
                "count",
            ]
        )

        assert result.returncode == 0
        assert result.stdout.strip() == "42"

    def test_reads_top_level_field(self, tmp_path):
        """Given a TOML with name = 'foo' at top level,
        when reading --key name,
        then stdout is 'foo'."""
        toml_content = 'name = "foo"\n'
        (tmp_path / "data.toml").write_text(toml_content)

        result = _run_read_toml(
            [
                "--file",
                str(tmp_path / "data.toml"),
                "--key",
                "name",
            ]
        )

        assert result.returncode == 0
        assert result.stdout.strip() == "foo"
