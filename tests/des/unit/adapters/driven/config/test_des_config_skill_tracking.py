"""Unit tests for DESConfig skill tracking properties.

Tests the new skill_tracking_enabled and skill_tracking_strategy properties.

Test Budget: 3 behaviors x 2 = 6 max. Actual: 5 tests (1 parametrized).

Behaviors:
1. Default is disabled
2. Config file enables tracking
3. Environment variable overrides config
"""

import json

import pytest

from des.adapters.driven.config.des_config import DESConfig


class TestSkillTrackingDefaultDisabled:
    """Skill tracking defaults to disabled when no config is present."""

    def test_default_disabled_when_no_config(self, tmp_path) -> None:
        """No config file means skill tracking is disabled."""
        config_file = tmp_path / ".nwave" / "des-config.json"

        config = DESConfig(config_path=config_file)

        assert config.skill_tracking_enabled is False
        assert config.skill_tracking_strategy == "disabled"


class TestSkillTrackingEnabledViaConfig:
    """Skill tracking is enabled when config file sets a non-disabled strategy."""

    @pytest.mark.parametrize(
        "strategy,expected_enabled",
        [
            ("passive-logging", True),
            ("token-tracking", True),
            ("disabled", False),
        ],
        ids=["passive_logging", "token_tracking", "disabled"],
    )
    def test_enabled_via_config_strategy(
        self, tmp_path, strategy, expected_enabled
    ) -> None:
        """Skill tracking enabled depends on strategy value in config."""
        config_file = tmp_path / ".nwave" / "des-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            json.dumps({"skill_tracking": strategy}), encoding="utf-8"
        )

        config = DESConfig(config_path=config_file)

        assert config.skill_tracking_enabled is expected_enabled
        assert config.skill_tracking_strategy == strategy


class TestSkillTrackingEnvVarOverride:
    """DES_SKILL_TRACKING env var overrides config file."""

    def test_env_var_true_enables_tracking(self, tmp_path, monkeypatch) -> None:
        """DES_SKILL_TRACKING=true enables tracking regardless of config."""
        config_file = tmp_path / ".nwave" / "des-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            json.dumps({"skill_tracking": "disabled"}), encoding="utf-8"
        )
        monkeypatch.setenv("DES_SKILL_TRACKING", "true")

        config = DESConfig(config_path=config_file)

        assert config.skill_tracking_enabled is True

    def test_env_var_false_disables_tracking(self, tmp_path, monkeypatch) -> None:
        """DES_SKILL_TRACKING=false disables tracking regardless of config."""
        config_file = tmp_path / ".nwave" / "des-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            json.dumps({"skill_tracking": "token-tracking"}), encoding="utf-8"
        )
        monkeypatch.setenv("DES_SKILL_TRACKING", "false")

        config = DESConfig(config_path=config_file)

        assert config.skill_tracking_enabled is False
