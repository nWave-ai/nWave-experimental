"""
Unit tests for HousekeepingConfig value object.

Tests HousekeepingConfig dataclass behavior:
- Zero-argument construction with all defaults
- Immutability (frozen dataclass)

Test Budget: 2 behaviors x 2 = 4 max. Actual: 2 tests.
"""

import dataclasses

import pytest


class TestHousekeepingConfigDefaults:
    """Test HousekeepingConfig is constructible with zero arguments."""

    def test_constructible_with_zero_arguments(self):
        """HousekeepingConfig can be constructed with no arguments using all defaults."""
        from des.application.housekeeping_service import HousekeepingConfig

        cfg = HousekeepingConfig()

        assert cfg.enabled is True
        assert cfg.audit_retention_days == 7
        assert cfg.signal_staleness_hours == 4
        assert cfg.skill_log_max_bytes == 1_048_576


class TestHousekeepingConfigImmutability:
    """Test HousekeepingConfig is a frozen dataclass (immutable)."""

    def test_is_frozen_dataclass(self):
        """HousekeepingConfig raises FrozenInstanceError when any field is mutated."""
        from des.application.housekeeping_service import HousekeepingConfig

        cfg = HousekeepingConfig()

        with pytest.raises(dataclasses.FrozenInstanceError):
            cfg.enabled = False  # type: ignore[misc]
