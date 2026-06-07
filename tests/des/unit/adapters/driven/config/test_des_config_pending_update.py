"""Unit tests for DESConfig pending_update flag I/O.

Test Budget: 4 behaviors x 2 = 8 max. Actual: 5 tests.

Behaviors:
1. pending_update_path returns ~/.nwave/pending-update.json
2. save_pending_update_state writes JSON via flag.to_dict() + ensures .gitignore
3. read_pending_update returns None when file missing or invalid JSON
4. clear_pending_update removes file idempotently
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.adapters.driven.config.des_config import DESConfig
from des.domain.pending_update_flag import PendingUpdateFlag


@pytest.fixture
def config(tmp_path, monkeypatch) -> DESConfig:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cfg_file = tmp_path / ".nwave" / "des-config.json"
    return DESConfig(config_path=cfg_file)


class TestPendingUpdatePath:
    def test_returns_home_nwave_pending_update_json(
        self, config: DESConfig, tmp_path: Path
    ) -> None:
        assert config.pending_update_path == tmp_path / ".nwave" / "pending-update.json"


class TestSavePendingUpdateState:
    def test_writes_flag_as_json_and_ensures_gitignore(
        self, config: DESConfig, tmp_path: Path
    ) -> None:
        flag = PendingUpdateFlag(
            pm="pipx",
            pm_binary_abspath="/usr/bin/pipx",
            target_version="3.11.0",
            requested_at="2026-04-16T00:00:00Z",
        )

        config.save_pending_update_state(flag)

        persisted = json.loads(config.pending_update_path.read_text(encoding="utf-8"))
        assert persisted == flag.to_dict()
        gitignore = tmp_path / ".nwave" / ".gitignore"
        assert gitignore.exists()


class TestReadPendingUpdate:
    def test_returns_none_when_file_missing(self, config: DESConfig) -> None:
        assert config.read_pending_update() is None

    def test_returns_none_when_json_invalid(
        self, config: DESConfig, tmp_path: Path
    ) -> None:
        (tmp_path / ".nwave").mkdir(parents=True, exist_ok=True)
        config.pending_update_path.write_text("not json {", encoding="utf-8")
        assert config.read_pending_update() is None

    def test_round_trips_flag(self, config: DESConfig) -> None:
        flag = PendingUpdateFlag(
            pm="uv",
            pm_binary_abspath="/usr/local/bin/uv",
            target_version="3.12.1",
            requested_at="2026-04-16T00:00:00Z",
            attempt_count=1,
            last_error="boom",
        )
        config.save_pending_update_state(flag)

        read = config.read_pending_update()

        assert read == flag


class TestClearPendingUpdate:
    def test_removes_file_when_present(self, config: DESConfig, tmp_path: Path) -> None:
        flag = PendingUpdateFlag(
            pm="pipx",
            pm_binary_abspath="/usr/bin/pipx",
            target_version="3.11.0",
            requested_at="2026-04-16T00:00:00Z",
        )
        config.save_pending_update_state(flag)
        assert config.pending_update_path.exists()

        config.clear_pending_update()

        assert not config.pending_update_path.exists()

    def test_is_idempotent_when_file_missing(self, config: DESConfig) -> None:
        # Should not raise
        config.clear_pending_update()
        config.clear_pending_update()
