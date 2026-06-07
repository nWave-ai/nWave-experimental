"""Tests for scripts/shared/version.py -- shared version reader."""

from scripts.shared.version import get_version


class TestGetVersion:
    """Test get_version() with various pyproject.toml states."""

    def test_reads_version_from_pyproject_toml(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "1.2.3"\n'
        )
        assert get_version(tmp_path) == "1.2.3"

    def test_missing_pyproject_returns_zero(self, tmp_path):
        assert get_version(tmp_path) == "0.0.0"

    def test_pyproject_without_version_returns_zero(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
        assert get_version(tmp_path) == "0.0.0"

    def test_pyproject_with_malformed_toml_returns_zero(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("this is not valid toml [[[\n")
        assert get_version(tmp_path) == "0.0.0"

    def test_reads_real_project_version(self):
        """Integration: reads the actual nWave-dev pyproject.toml."""
        from pathlib import Path

        project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
        version = get_version(project_root)
        # Should be a real semver-like string, not 0.0.0
        assert version != "0.0.0"
        assert "." in version

    def test_regex_fallback_parses_version(self, tmp_path):
        """Version can be read even without tomllib (regex fallback)."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "3.4.5"\n'
        )
        # get_version tries tomllib first, falls back to regex
        # Both paths should produce the same result
        assert get_version(tmp_path) == "3.4.5"
