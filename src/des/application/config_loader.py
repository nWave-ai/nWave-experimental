"""
Configuration loader for DES system.

Loads and validates configuration including turn limits by task type.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from des.domain.turn_config import TurnLimitConfig


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""

    pass


class ConfigLoader:
    """
    Single configuration loader for DES turn limits, with validation.

    Loads turn limits from a JSON file and exposes them by task type. The
    canonical defaults are sourced once from ``src/des/config/des_defaults.yaml``
    (the config SSOT) and are the single representation of the turn-limit
    defaults across DES:
    - quick=15
    - background=25
    - standard=30 (default)
    - research=35
    - complex=50

    Defaults to standard (30) if type not specified. The typed
    ``des.domain.turn_config.TurnLimitConfig`` value object is the typed SSOT
    for the quick/standard/complex triple; ``get_default_config`` returns it.
    """

    # Canonical defaults — single source, aligned with src/des/config/des_defaults.yaml.
    DEFAULT_TURN_LIMITS = {
        "quick": 15,
        "background": 25,
        "standard": 30,
        "research": 35,
        "complex": 50,
    }

    def __init__(self, config_path: str):
        """
        Initialize ConfigLoader.

        Args:
            config_path: Path to JSON configuration file

        Raises:
            ConfigValidationError: If configuration is invalid
        """
        self.config_path = Path(config_path)
        self.turn_limits = self._load_turn_limits()

    def _load_turn_limits(self) -> dict[str, int]:
        """
        Load turn limits from config file with validation.

        Returns:
            Dictionary mapping task type to turn limit

        Raises:
            ConfigValidationError: If turn limits are invalid
        """
        if not self.config_path.exists():
            return self.DEFAULT_TURN_LIMITS.copy()

        try:
            with open(self.config_path) as f:
                config = json.load(f)
        except (OSError, json.JSONDecodeError):
            return self.DEFAULT_TURN_LIMITS.copy()

        turn_limits = config.get("turn_limits", {})

        for task_type, limit in turn_limits.items():
            if not isinstance(limit, int) or limit <= 0:
                raise ConfigValidationError(
                    f"Turn limit for '{task_type}' must be positive integer, got {limit}"
                )

        return turn_limits

    def get_turn_limit(self, task_type: str | None) -> int:
        """
        Get turn limit for task type.

        Args:
            task_type: Task type (quick/standard/complex) or None

        Returns:
            Turn limit for task type, or standard default (30) if not found
        """
        if task_type is None or task_type not in self.turn_limits:
            return self.turn_limits.get(
                "standard", self.DEFAULT_TURN_LIMITS["standard"]
            )

        return self.turn_limits[task_type]

    @classmethod
    def get_default_config(cls) -> TurnLimitConfig:
        """Provide the canonical default turn limits as the typed SSOT VO.

        Returns:
            TurnLimitConfig built from the canonical defaults
            (src/des/config/des_defaults.yaml): quick=15, standard=30, complex=50.
        """
        # Local import: des.application is imported before des.domain during
        # des package initialization; a module-level import would create a
        # partial-initialization cycle.
        from des.domain.turn_config import TurnLimitConfig

        return TurnLimitConfig(
            quick=cls.DEFAULT_TURN_LIMITS["quick"],
            standard=cls.DEFAULT_TURN_LIMITS["standard"],
            complex=cls.DEFAULT_TURN_LIMITS["complex"],
        )
