"""Tests for scripts/release/bump_version.py

Extracts inline version-bump logic from release-prod.yml into a testable
standalone script.  Tests run the script via subprocess to validate the
real CLI contract.

BDD scenario mapping:
  - release-prod.yml "Bump version in pyproject.toml and framework-catalog.yaml"
  - Replaces fragile shell-heredoc inline Python blocks (P4 + P5)
"""

from __future__ import annotations

import subprocess
import sys


def _run_bump(args: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    """Run bump_version.py as a subprocess and return the result."""
    return subprocess.run(
        [sys.executable, "-m", "scripts.release.bump_version", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


# ---------------------------------------------------------------------------
# Pyproject.toml bumping
# ---------------------------------------------------------------------------


class TestPyprojectBump:
    """Version bumping in pyproject.toml."""

    def test_bumps_version_in_pyproject_toml(self, tmp_path):
        """Given a pyproject.toml with version = "0.0.0",
        when bumping to "1.2.3",
        then the file contains version = "1.2.3"."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "example"\nversion = "0.0.0"\n')

        result = _run_bump(["--version", "1.2.3", "--pyproject", str(pyproject)])

        assert result.returncode == 0
        content = pyproject.read_text()
        assert 'version = "1.2.3"' in content

    def test_all_version_fields_are_bumped(self, tmp_path):
        """Given a pyproject.toml with version in both [project] and [tool.commitizen],
        when bumping,
        then ALL version = "..." occurrences are updated (keeps CZ in sync)."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "example"\nversion = "0.0.0"\n\n'
            "[tool.commitizen]\n"
            'version = "0.0.0"\n'
        )

        result = _run_bump(["--version", "1.2.3", "--pyproject", str(pyproject)])

        assert result.returncode == 0
        content = pyproject.read_text()
        assert content.count('version = "1.2.3"') == 2

    def test_public_version_floor_not_clobbered(self, tmp_path):
        """Given a pyproject.toml with project.version, tool.commitizen.version,
        AND tool.nwave.public_version = "1.1.0",
        when bumping to "1.3.0",
        then public_version stays "1.1.0" (it's a manual floor, not a release version).

        Regression: regex r'version = "[^"]+"' matched the substring
        'version = "1.1.0"' inside 'public_version = "1.1.0"', silently
        overwriting the floor on every stable release."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "nwave"\nversion = "1.2.0"\n\n'
            "[tool.nwave]\n"
            'public_version = "1.1.0"\n\n'
            "[tool.commitizen]\n"
            'version = "1.2.0"\n'
        )

        result = _run_bump(["--version", "1.3.0", "--pyproject", str(pyproject)])

        assert result.returncode == 0
        content = pyproject.read_text()
        assert 'public_version = "1.1.0"' in content, (
            f"public_version was clobbered! Content:\n{content}"
        )
        assert content.count('version = "1.3.0"') == 2, (
            "project.version and tool.commitizen.version must both be 1.3.0"
        )

    def test_missing_pyproject_exits_with_error(self, tmp_path):
        """Given --pyproject points to nonexistent file,
        then exit code is 1."""
        result = _run_bump(
            ["--version", "1.2.3", "--pyproject", str(tmp_path / "nope.toml")]
        )

        assert result.returncode == 1
        assert "not found" in result.stderr.lower() or "error" in result.stderr.lower()


# ---------------------------------------------------------------------------
# Catalog YAML bumping
# ---------------------------------------------------------------------------


class TestCatalogBump:
    """Version bumping in framework-catalog.yaml."""

    def test_bumps_version_in_catalog_yaml(self, tmp_path):
        """Given a catalog YAML with version: "0.0.0",
        when bumping to "1.2.3",
        then the file contains version: '1.2.3'."""
        catalog = tmp_path / "catalog.yaml"
        catalog.write_text("name: nWave\nversion: '0.0.0'\ndescription: test\n")

        result = _run_bump(["--version", "1.2.3", "--catalog", str(catalog)])

        assert result.returncode == 0
        content = catalog.read_text()
        assert "version: 1.2.3" in content or "version: '1.2.3'" in content

    def test_preserves_other_catalog_fields(self, tmp_path):
        """Given a catalog with name, version, and description,
        when bumping version,
        then name and description are unchanged."""
        catalog = tmp_path / "catalog.yaml"
        catalog.write_text("name: nWave\nversion: '0.0.0'\ndescription: My framework\n")

        result = _run_bump(["--version", "1.2.3", "--catalog", str(catalog)])

        assert result.returncode == 0
        content = catalog.read_text()
        assert "name: nWave" in content
        assert "description: My framework" in content

    def test_missing_catalog_exits_with_error(self, tmp_path):
        """Given --catalog points to nonexistent file,
        then exit code is 1."""
        result = _run_bump(
            ["--version", "1.2.3", "--catalog", str(tmp_path / "nope.yaml")]
        )

        assert result.returncode == 1
        assert "not found" in result.stderr.lower() or "error" in result.stderr.lower()


# ---------------------------------------------------------------------------
# Both files in a single invocation
# ---------------------------------------------------------------------------


class TestBothFiles:
    """Bumping both files in a single invocation."""

    def test_bumps_both_pyproject_and_catalog(self, tmp_path):
        """Given both --pyproject and --catalog are provided,
        when bumping to "1.2.3",
        then both files are updated."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "example"\nversion = "0.0.0"\n')
        catalog = tmp_path / "catalog.yaml"
        catalog.write_text("name: nWave\nversion: '0.0.0'\n")

        result = _run_bump(
            [
                "--version",
                "1.2.3",
                "--pyproject",
                str(pyproject),
                "--catalog",
                str(catalog),
            ]
        )

        assert result.returncode == 0
        assert 'version = "1.2.3"' in pyproject.read_text()
        catalog_content = catalog.read_text()
        assert (
            "version: 1.2.3" in catalog_content or "version: '1.2.3'" in catalog_content
        )


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class TestValidation:
    """Input validation."""

    def test_no_files_specified_exits_with_error(self):
        """Given neither --pyproject nor --catalog is provided,
        then exit code is non-zero with error message."""
        result = _run_bump(["--version", "1.2.3"])

        assert result.returncode != 0
        assert (
            "at least one" in result.stderr.lower() or "error" in result.stderr.lower()
        )
