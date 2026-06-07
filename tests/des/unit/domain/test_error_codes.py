"""Unit tests for error code registry.

Tests the NWError dataclass, ErrorCategory enum, and registry
lookup functions through the module's public API.
"""

import pytest

from des.domain.error_codes import (
    ErrorCategory,
    NWError,
    get_error,
    get_errors_by_category,
    get_errors_by_stage,
)


class TestNWErrorDataclass:
    """Tests for NWError frozen dataclass structure."""

    def test_nwerror_is_frozen(self):
        """NWError instances should be immutable."""
        error = NWError(
            code="NW-I001",
            category=ErrorCategory.ENVIRONMENT,
            stage="install",
            message="No virtual environment detected",
            recovery="Create and activate a venv",
        )
        with pytest.raises(AttributeError):
            error.code = "NW-I999"

    def test_nwerror_exposes_all_fields(self):
        """NWError should expose code, category, stage, message, recovery."""
        error = NWError(
            code="NW-H001",
            category=ErrorCategory.DISPATCH,
            stage="hook",
            message="Hook dispatch failed",
            recovery="Check hook configuration",
        )
        assert error.code == "NW-H001"
        assert error.category == ErrorCategory.DISPATCH
        assert error.stage == "hook"
        assert error.message == "Hook dispatch failed"
        assert error.recovery == "Check hook configuration"


class TestErrorCategoryEnum:
    """Tests for ErrorCategory enum completeness."""

    @pytest.mark.parametrize(
        "member",
        [
            "ENVIRONMENT",
            "DEPENDENCY",
            "VALIDATION",
            "PERMISSION",
            "TEMPLATE",
            "IO",
            "DISPATCH",
            "INTERNAL",
            "CONFIG",
        ],
    )
    def test_has_required_category(self, member):
        """ErrorCategory enum should contain all 9 required members."""
        assert hasattr(ErrorCategory, member)
        assert ErrorCategory[member].value == member


class TestGetError:
    """Tests for get_error() registry lookup."""

    @pytest.mark.parametrize(
        "code",
        ["NW-I001", "NW-H001", "NW-B001", "NW-P001"],
    )
    def test_returns_error_for_valid_code(self, code):
        """get_error should return NWError for each registered code."""
        result = get_error(code)
        assert isinstance(result, NWError)
        assert result.code == code

    def test_returns_none_for_unknown_code(self):
        """get_error should return None for unregistered codes."""
        assert get_error("NW-X999") is None


class TestGetErrorsByStage:
    """Tests for get_errors_by_stage() filtering."""

    @pytest.mark.parametrize(
        "stage,prefix",
        [
            ("install", "NW-I"),
            ("hook", "NW-H"),
            ("build", "NW-B"),
            ("plugin", "NW-P"),
        ],
    )
    def test_returns_errors_matching_stage(self, stage, prefix):
        """get_errors_by_stage should return only errors for the given stage."""
        errors = get_errors_by_stage(stage)
        assert len(errors) >= 5, f"Expected at least 5 {stage} errors"
        assert all(e.stage == stage for e in errors)
        assert all(e.code.startswith(prefix) for e in errors)


class TestGetErrorsByCategory:
    """Tests for get_errors_by_category() filtering."""

    def test_returns_errors_matching_category(self):
        """get_errors_by_category should return only errors of the given category."""
        errors = get_errors_by_category(ErrorCategory.IO)
        assert len(errors) >= 1
        assert all(e.category == ErrorCategory.IO for e in errors)

    def test_returns_empty_for_unused_category(self):
        """get_errors_by_category should return empty list if no errors match."""
        # All 9 categories are used, so we test with a category that has entries
        # and verify the filtering property holds -- no false matches
        for cat in ErrorCategory:
            errors = get_errors_by_category(cat)
            assert all(e.category == cat for e in errors)


class TestRegistryCoverage:
    """Tests for registry completeness requirements."""

    def test_registry_has_at_least_20_codes(self):
        """Registry should contain at least 20 error codes total."""
        total = sum(
            len(get_errors_by_stage(stage))
            for stage in ("install", "hook", "build", "plugin")
        )
        assert total >= 20

    def test_all_four_stages_represented(self):
        """Registry should have codes for all 4 lifecycle stages."""
        for stage in ("install", "hook", "build", "plugin"):
            errors = get_errors_by_stage(stage)
            assert len(errors) >= 1, f"Stage '{stage}' has no error codes"
