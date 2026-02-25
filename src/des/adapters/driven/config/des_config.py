"""
DES Configuration Adapter - Driven Port Implementation.

Loads configuration from .nwave/des-config.json and provides access to settings.
Falls back to safe defaults (audit logging ON) when file is missing or invalid.

Hexagonal Architecture:
- DRIVEN ADAPTER: Implements configuration port (driven by business logic)
- ON BY DEFAULT: Audit logging enabled unless explicitly disabled in config
"""

import json
import os
from pathlib import Path
from typing import Any


class DESConfig:
    """
    Configuration loader for DES settings.

    Loads configuration from .nwave/des-config.json with on-by-default audit logging.
    Does NOT auto-create config files.
    """

    def __init__(
        self,
        config_path: Path | None = None,
        cwd: Path | None = None,
    ):
        """
        Initialize DESConfig.

        Args:
            config_path: Optional explicit path to config file
            cwd: Optional working directory (defaults to Path.cwd());
                 used to resolve .nwave/des-config.json when config_path is None
        """
        if config_path is None:
            effective_cwd = cwd or Path.cwd()
            config_path = effective_cwd / ".nwave" / "des-config.json"

        self._config_path = config_path
        self._config_data = self._load_configuration()

    def _load_configuration(self) -> dict[str, Any]:
        """
        Load configuration from JSON file.

        Returns:
            Configuration dictionary, empty dict if loading fails
        """
        if not self._config_path.exists():
            return {}

        try:
            return json.loads(self._config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    @property
    def skill_tracking_enabled(self) -> bool:
        """
        Check if skill loading tracking is enabled.

        Priority: DES_SKILL_TRACKING env var > config file > default (False).

        Returns:
            True if skill tracking enabled, False otherwise (defaults to False)
        """
        env_override = os.environ.get("DES_SKILL_TRACKING")
        if env_override is not None:
            return env_override.lower() in ("true", "1", "yes")
        strategy = self._config_data.get("skill_tracking", "disabled")
        return strategy != "disabled"

    @property
    def skill_tracking_strategy(self) -> str:
        """
        Get skill tracking strategy.

        Returns:
            Strategy string: "disabled", "passive-logging", or "token-tracking"
        """
        return self._config_data.get("skill_tracking", "disabled")

    @property
    def audit_logging_enabled(self) -> bool:
        """
        Check if audit logging is enabled.

        Priority: DES_AUDIT_LOGGING_ENABLED env var > config file > default (True).

        Returns:
            True if audit logging enabled, False otherwise (defaults to True)
        """
        env_override = os.environ.get("DES_AUDIT_LOGGING_ENABLED")
        if env_override is not None:
            return env_override.lower() in ("true", "1", "yes")
        return self._config_data.get("audit_logging_enabled", True)

    @property
    def rigor_profile(self) -> str:
        """Get rigor profile name. Default: 'standard'."""
        return self._config_data.get("rigor", {}).get("profile", "standard")

    @property
    def rigor_agent_model(self) -> str:
        """Get agent model from rigor config. Default: 'sonnet'."""
        return self._config_data.get("rigor", {}).get("agent_model", "sonnet")

    @property
    def rigor_reviewer_model(self) -> str:
        """Get reviewer model. Default: 'haiku'."""
        return self._config_data.get("rigor", {}).get("reviewer_model", "haiku")

    @property
    def rigor_tdd_phases(self) -> tuple[str, ...]:
        """Get TDD phases as tuple. Default: full 5-phase."""
        phases = self._config_data.get("rigor", {}).get(
            "tdd_phases",
            ["PREPARE", "RED_ACCEPTANCE", "RED_UNIT", "GREEN", "COMMIT"],
        )
        return tuple(phases)

    @property
    def rigor_review_enabled(self) -> bool:
        """Check if peer review is enabled. Default: True."""
        return self._config_data.get("rigor", {}).get("review_enabled", True)

    @property
    def rigor_double_review(self) -> bool:
        """Check if double review is enabled. Default: False."""
        return self._config_data.get("rigor", {}).get("double_review", False)

    @property
    def rigor_mutation_enabled(self) -> bool:
        """Check if mutation testing is enabled. Default: False."""
        return self._config_data.get("rigor", {}).get("mutation_enabled", False)

    @property
    def rigor_refactor_pass(self) -> bool:
        """Check if refactoring pass is enabled. Default: True."""
        return self._config_data.get("rigor", {}).get("refactor_pass", True)
