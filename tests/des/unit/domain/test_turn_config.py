"""Unit tests for turn limit configuration module.

Business Value: Validates task type-based turn limits for fine-grained control.
"""

from des.domain.turn_config import TurnLimitConfig


class TestTurnLimitConfig:
    """Tests for TurnLimitConfig value object."""

    def test_turn_limit_config_stores_limits_by_task_type(self):
        """TurnLimitConfig provides task type-specific turn limits."""
        config = TurnLimitConfig(quick=20, standard=50, complex=100)

        assert config.quick == 20
        assert config.standard == 50
        assert config.complex == 100

    def test_turn_limit_config_has_default_fallback(self):
        """TurnLimitConfig defaults to standard limit when type unknown."""
        config = TurnLimitConfig(quick=20, standard=50, complex=100)

        assert config.get_limit_for_type("standard") == 50
        assert config.get_limit_for_type("unknown_type") == 50  # Falls back to standard
