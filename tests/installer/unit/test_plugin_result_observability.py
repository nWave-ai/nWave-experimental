"""
Tests for PluginResult observability fields (duration_ms, error_code).

Step 02-01: Extend PluginResult with duration_ms and error_code fields.

Acceptance Criteria:
  AC1: PluginResult created with only (success, plugin_name, message) still works
  AC2: PluginResult accepts optional duration_ms (float | None) and error_code (str | None)
  AC3: No TypeError when existing code creates PluginResult without new fields
"""

from pathlib import Path

import pytest

from scripts.install.plugins.base import PluginResult


class TestPluginResultObservabilityFields:
    """PluginResult should support optional duration_ms and error_code fields."""

    def test_backward_compatible_creation_without_new_fields(self):
        """AC1 + AC3: Existing callers that omit duration_ms and error_code
        must not raise TypeError."""
        result = PluginResult(
            success=True,
            plugin_name="test-plugin",
            message="Installed successfully",
        )

        assert result.success is True
        assert result.plugin_name == "test-plugin"
        assert result.message == "Installed successfully"
        assert result.duration_ms is None
        assert result.error_code is None

    def test_accepts_explicit_duration_ms_and_error_code(self):
        """AC2: PluginResult accepts duration_ms and error_code when provided."""
        result = PluginResult(
            success=False,
            plugin_name="des",
            message="Hook validation failed",
            duration_ms=1523.7,
            error_code="NW-I-0042",
        )

        assert result.duration_ms == 1523.7
        assert result.error_code == "NW-I-0042"

    @pytest.mark.parametrize(
        "duration_ms,error_code",
        [
            (None, None),
            (0.0, None),
            (None, "NW-I-0001"),
            (250.5, "NW-I-0010"),
        ],
        ids=[
            "both-none",
            "zero-duration-no-error",
            "no-duration-with-error",
            "both-present",
        ],
    )
    def test_field_combinations(self, duration_ms, error_code):
        """AC2: All combinations of None and explicit values work correctly."""
        result = PluginResult(
            success=True,
            plugin_name="skills",
            message="OK",
            duration_ms=duration_ms,
            error_code=error_code,
        )

        assert result.duration_ms == duration_ms
        assert result.error_code == error_code

    def test_existing_fields_unaffected_by_new_fields(self):
        """AC1: Existing fields (errors, installed_files) still work alongside
        new observability fields."""
        result = PluginResult(
            success=True,
            plugin_name="templates",
            message="3 files installed",
            errors=["warning: file overwritten"],
            installed_files=[Path("/home/user/.claude/templates/tdd.json")],
            duration_ms=800.0,
            error_code=None,
        )

        assert result.errors == ["warning: file overwritten"]
        assert len(result.installed_files) == 1
        assert result.duration_ms == 800.0
        assert result.error_code is None
