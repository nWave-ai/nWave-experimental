"""Unit tests for DESConfig log_level and log_enabled properties.

Tests the 3-tier priority resolution:
  env var > config file > default

Test Budget: 8 behaviors x 2 = 16 max. Actual: 8 tests (3 parametrized).

Behaviors:
1. log_level defaults to "WARN" when no env/config
2. log_level reads from config file
3. log_level env var NW_LOG_LEVEL overrides config
4. log_enabled defaults to False when no env/config
5. log_enabled reads from config file
6. log_enabled env var NW_LOG overrides config
7. _get_nwave_log_writer returns NullNWaveLogWriter when disabled
8. _get_nwave_log_writer returns JsonlNWaveLogWriter when enabled with correct level
"""

import json

import pytest

from des.adapters.driven.config.des_config import DESConfig


class TestLogLevelDefault:
    """log_level defaults to WARN when no env var and no config key."""

    def test_defaults_to_warn_when_no_config(self, tmp_path) -> None:
        """log_level returns 'WARN' when config file is missing."""
        config_file = tmp_path / ".nwave" / "des-config.json"

        config = DESConfig(config_path=config_file)

        assert config.log_level == "WARN"


class TestLogLevelFromConfig:
    """log_level reads from config file log_level key."""

    @pytest.mark.parametrize(
        "config_value,expected",
        [
            ("debug", "DEBUG"),
            ("info", "INFO"),
            ("warn", "WARN"),
            ("error", "ERROR"),
        ],
        ids=["debug", "info", "warn", "error"],
    )
    def test_reads_log_level_from_config_and_uppercases(
        self, tmp_path, config_value, expected
    ) -> None:
        """log_level reads value from config and returns it uppercased."""
        config_file = tmp_path / ".nwave" / "des-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            json.dumps({"log_level": config_value}), encoding="utf-8"
        )

        config = DESConfig(config_path=config_file)

        assert config.log_level == expected


class TestLogLevelEnvVarOverride:
    """NW_LOG_LEVEL env var overrides config file."""

    def test_env_var_overrides_config(self, tmp_path, monkeypatch) -> None:
        """NW_LOG_LEVEL env var takes priority over config file value."""
        config_file = tmp_path / ".nwave" / "des-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(json.dumps({"log_level": "warn"}), encoding="utf-8")
        monkeypatch.setenv("NW_LOG_LEVEL", "debug")

        config = DESConfig(config_path=config_file)

        assert config.log_level == "DEBUG"


class TestLogEnabledDefault:
    """log_enabled defaults to False when no env var and no config key."""

    def test_defaults_to_false_when_no_config(self, tmp_path) -> None:
        """log_enabled returns False when config file is missing."""
        config_file = tmp_path / ".nwave" / "des-config.json"

        config = DESConfig(config_path=config_file)

        assert config.log_enabled is False


class TestLogEnabledFromConfig:
    """log_enabled reads from config file log_enabled key."""

    @pytest.mark.parametrize(
        "config_value,expected",
        [
            (True, True),
            (False, False),
        ],
        ids=["enabled", "disabled"],
    )
    def test_reads_log_enabled_from_config(
        self, tmp_path, config_value, expected
    ) -> None:
        """log_enabled reads boolean value from config file."""
        config_file = tmp_path / ".nwave" / "des-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            json.dumps({"log_enabled": config_value}), encoding="utf-8"
        )

        config = DESConfig(config_path=config_file)

        assert config.log_enabled is expected


class TestLogEnabledEnvVarOverride:
    """NW_LOG env var overrides config file."""

    @pytest.mark.parametrize(
        "env_value,expected",
        [
            ("true", True),
            ("1", True),
            ("yes", True),
            ("false", False),
            ("0", False),
            ("no", False),
        ],
        ids=["true", "1", "yes", "false", "0", "no"],
    )
    def test_env_var_overrides_config(
        self, tmp_path, monkeypatch, env_value, expected
    ) -> None:
        """NW_LOG env var takes priority over config file value."""
        config_file = tmp_path / ".nwave" / "des-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            json.dumps({"log_enabled": not expected}), encoding="utf-8"
        )
        monkeypatch.setenv("NW_LOG", env_value)

        config = DESConfig(config_path=config_file)

        assert config.log_enabled is expected


class TestGetNwaveLogWriterFactory:
    """_get_nwave_log_writer returns correct writer type based on config."""

    def test_returns_null_writer_when_disabled(self, tmp_path) -> None:
        """Returns NullNWaveLogWriter when log_enabled is False."""
        from des.adapters.driven.logging.null_nwave_log_writer import (
            NullNWaveLogWriter,
        )
        from des.adapters.drivers.hooks.hook_protocol import (
            _get_nwave_log_writer,
        )

        config_file = tmp_path / ".nwave" / "des-config.json"

        config = DESConfig(config_path=config_file)
        writer = _get_nwave_log_writer(config)

        assert isinstance(writer, NullNWaveLogWriter)

    def test_returns_jsonl_writer_when_enabled_with_correct_level(
        self, tmp_path
    ) -> None:
        """Returns JsonlNWaveLogWriter with log_level set when log_enabled is True."""
        from des.adapters.driven.logging.jsonl_nwave_log_writer import (
            JsonlNWaveLogWriter,
        )
        from des.adapters.drivers.hooks.hook_protocol import (
            _get_nwave_log_writer,
        )
        from des.ports.driven_ports.nwave_log_writer import LogLevel

        config_file = tmp_path / ".nwave" / "des-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            json.dumps({"log_enabled": True, "log_level": "debug"}),
            encoding="utf-8",
        )

        config = DESConfig(config_path=config_file)
        writer = _get_nwave_log_writer(config)

        assert isinstance(writer, JsonlNWaveLogWriter)
        assert writer._level == LogLevel.DEBUG
