"""
Unit tests for DESConfig update_check properties and save method.

Tests the update_check_frequency, update_check_last_checked,
update_check_skipped_versions read properties and save_update_check_state
write method.

Test Budget: 6 behaviors x 2 = 12 max. Actual: 10 tests (1 parametrized).

Behaviors:
1. update_check_frequency returns None when update_check key is entirely absent
2. update_check_frequency returns 'daily' when key present but frequency absent
3. update_check_last_checked defaults to None when key absent
4. update_check_skipped_versions defaults to empty list when key absent
5. save_update_check_state writes frequency, last_checked, skipped_versions
6. save_update_check_state preserves unrelated config keys (read-modify-write)
"""

import json

import pytest

from des.adapters.driven.config.des_config import DESConfig


class TestUpdateCheckFrequencyDefault:
    """update_check_frequency contract: None when key absent, 'daily' when key present."""

    @pytest.mark.parametrize(
        "config_content",
        [
            {},
            {"rigor": {"profile": "standard"}},
        ],
        ids=["empty_config", "no_update_check_key"],
    )
    def test_returns_none_when_update_check_key_entirely_absent(
        self, tmp_path, config_content
    ) -> None:
        """update_check_frequency returns None when update_check key is absent (first run)."""
        config_file = tmp_path / ".nwave" / "des-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(json.dumps(config_content), encoding="utf-8")

        config = DESConfig(config_path=config_file)

        assert config.update_check_frequency is None

    def test_returns_none_when_config_file_missing(self, tmp_path) -> None:
        """update_check_frequency returns None when config file does not exist (first run)."""
        config_file = tmp_path / ".nwave" / "des-config.json"

        config = DESConfig(config_path=config_file)

        assert config.update_check_frequency is None

    def test_returns_daily_when_update_check_key_present_but_frequency_absent(
        self, tmp_path
    ) -> None:
        """update_check_frequency defaults to 'daily' when key exists but frequency absent."""
        config_file = tmp_path / ".nwave" / "des-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(json.dumps({"update_check": {}}), encoding="utf-8")

        config = DESConfig(config_path=config_file)

        assert config.update_check_frequency == "daily"

    def test_returns_configured_frequency_when_set(self, tmp_path) -> None:
        """update_check_frequency returns value from config when explicitly set."""
        config_file = tmp_path / ".nwave" / "des-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            json.dumps({"update_check": {"frequency": "weekly"}}), encoding="utf-8"
        )

        config = DESConfig(config_path=config_file)

        assert config.update_check_frequency == "weekly"


class TestUpdateCheckLastCheckedDefault:
    """update_check_last_checked returns None when key is absent."""

    def test_returns_none_when_config_file_missing(self, tmp_path) -> None:
        """update_check_last_checked returns None when config file does not exist."""
        config_file = tmp_path / ".nwave" / "des-config.json"

        config = DESConfig(config_path=config_file)

        assert config.update_check_last_checked is None

    def test_returns_none_when_update_check_key_absent(self, tmp_path) -> None:
        """update_check_last_checked returns None when update_check key is absent."""
        config_file = tmp_path / ".nwave" / "des-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            json.dumps({"audit_logging_enabled": True}), encoding="utf-8"
        )

        config = DESConfig(config_path=config_file)

        assert config.update_check_last_checked is None

    def test_returns_iso_string_when_set(self, tmp_path) -> None:
        """update_check_last_checked returns ISO 8601 string when explicitly set."""
        config_file = tmp_path / ".nwave" / "des-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            json.dumps({"update_check": {"last_checked": "2026-02-25T10:00:00Z"}}),
            encoding="utf-8",
        )

        config = DESConfig(config_path=config_file)

        assert config.update_check_last_checked == "2026-02-25T10:00:00Z"


class TestUpdateCheckSkippedVersionsDefault:
    """update_check_skipped_versions returns empty list when key is absent."""

    def test_returns_empty_list_when_config_file_missing(self, tmp_path) -> None:
        """update_check_skipped_versions returns [] when config file does not exist."""
        config_file = tmp_path / ".nwave" / "des-config.json"

        config = DESConfig(config_path=config_file)

        assert config.update_check_skipped_versions == []

    def test_returns_list_of_skipped_versions_when_set(self, tmp_path) -> None:
        """update_check_skipped_versions returns configured list when set."""
        config_file = tmp_path / ".nwave" / "des-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            json.dumps({"update_check": {"skipped_versions": ["2.0.0", "2.1.0"]}}),
            encoding="utf-8",
        )

        config = DESConfig(config_path=config_file)

        assert config.update_check_skipped_versions == ["2.0.0", "2.1.0"]


class TestSaveUpdateCheckState:
    """save_update_check_state writes state to the config file."""

    def test_writes_all_fields_when_file_does_not_exist(self, tmp_path) -> None:
        """save_update_check_state creates update_check key when file is absent."""
        config_file = tmp_path / ".nwave" / "des-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)

        config = DESConfig(config_path=config_file)
        config.save_update_check_state(
            last_checked="2026-02-25T10:00:00Z",
            skipped_versions=["2.0.0"],
            frequency="weekly",
        )

        saved = json.loads(config_file.read_text(encoding="utf-8"))
        assert saved["update_check"]["last_checked"] == "2026-02-25T10:00:00Z"
        assert saved["update_check"]["skipped_versions"] == ["2.0.0"]
        assert saved["update_check"]["frequency"] == "weekly"

    def test_preserves_existing_frequency_when_none_passed(self, tmp_path) -> None:
        """save_update_check_state preserves frequency when None passed."""
        config_file = tmp_path / ".nwave" / "des-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            json.dumps({"update_check": {"frequency": "weekly"}}), encoding="utf-8"
        )

        config = DESConfig(config_path=config_file)
        config.save_update_check_state(
            last_checked="2026-02-25T10:00:00Z",
            skipped_versions=[],
            frequency=None,
        )

        saved = json.loads(config_file.read_text(encoding="utf-8"))
        assert saved["update_check"]["frequency"] == "weekly"
        assert saved["update_check"]["last_checked"] == "2026-02-25T10:00:00Z"

    def test_preserves_unrelated_config_keys(self, tmp_path) -> None:
        """save_update_check_state does not modify unrelated config keys."""
        config_file = tmp_path / ".nwave" / "des-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            json.dumps(
                {
                    "audit_logging_enabled": True,
                    "rigor": {"profile": "standard"},
                }
            ),
            encoding="utf-8",
        )

        config = DESConfig(config_path=config_file)
        config.save_update_check_state(
            last_checked="2026-02-25T10:00:00Z",
            skipped_versions=[],
        )

        saved = json.loads(config_file.read_text(encoding="utf-8"))
        assert saved["audit_logging_enabled"] is True
        assert saved["rigor"]["profile"] == "standard"
        assert saved["update_check"]["last_checked"] == "2026-02-25T10:00:00Z"
