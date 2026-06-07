"""Unit tests for PendingUpdateService.

Test Budget: 4 behaviors x 2 = 8 max. Actual: 4 tests.

Behaviors:
1. request_update persists PendingUpdateFlag via DESConfig
2. apply() with flag present calls port.upgrade and clears flag on success
3. apply() with no flag returns no-op success
4. apply() passes pm_binary_abspath and target_version from flag to port
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.adapters.driven.config.des_config import DESConfig
from des.adapters.driven.package_managers.fake_package_manager import (
    FakePackageManager,
)
from des.application.pending_update_service import PendingUpdateService
from des.domain.pending_update_flag import PendingUpdateFlag


@pytest.fixture
def config(tmp_path, monkeypatch) -> DESConfig:
    """DESConfig with HOME redirected to tmp_path."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # also patch Path.home resolution
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cfg_file = tmp_path / ".nwave" / "des-config.json"
    return DESConfig(config_path=cfg_file)


class TestRequestUpdate:
    def test_request_update_persists_flag_to_pending_update_path(
        self, config: DESConfig, tmp_path: Path
    ) -> None:
        pm = FakePackageManager()
        service = PendingUpdateService(config=config, pm=pm)

        service.request_update(
            pm="pipx",
            pm_binary_abspath="/usr/bin/pipx",
            target_version="3.11.0",
        )

        flag = config.read_pending_update()
        assert flag is not None
        assert flag.pm == "pipx"
        assert flag.pm_binary_abspath == "/usr/bin/pipx"
        assert flag.target_version == "3.11.0"


class TestApply:
    def test_apply_with_no_flag_returns_noop_success(self, config: DESConfig) -> None:
        pm = FakePackageManager()
        service = PendingUpdateService(config=config, pm=pm)

        result = service.apply()

        assert result.success is True
        assert result.error is None
        assert pm.calls == []

    def test_apply_invokes_port_with_flag_values_and_clears_on_success(
        self, config: DESConfig, tmp_path: Path
    ) -> None:
        pm = FakePackageManager()
        pm.will_succeed()
        uv_bin = tmp_path / "bin" / "uv"
        uv_bin.parent.mkdir(parents=True, exist_ok=True)
        uv_bin.write_text("#!/bin/sh\n")
        flag = PendingUpdateFlag(
            pm="uv",
            pm_binary_abspath=str(uv_bin),
            target_version="3.12.1",
            requested_at="2026-04-16T00:00:00Z",
        )
        config.save_pending_update_state(flag)
        service = PendingUpdateService(config=config, pm=pm)

        result = service.apply()

        assert result.success is True
        assert pm.calls == [(str(uv_bin), "3.12.1")]
        assert config.read_pending_update() is None  # cleared

    def test_apply_does_not_clear_flag_when_port_fails(
        self, config: DESConfig, tmp_path: Path
    ) -> None:
        pm = FakePackageManager()
        pm.will_fail("network error")
        pipx_bin = tmp_path / "bin" / "pipx"
        pipx_bin.parent.mkdir(parents=True, exist_ok=True)
        pipx_bin.write_text("#!/bin/sh\n")
        flag = PendingUpdateFlag(
            pm="pipx",
            pm_binary_abspath=str(pipx_bin),
            target_version="3.11.0",
            requested_at="2026-04-16T00:00:00Z",
        )
        config.save_pending_update_state(flag)
        service = PendingUpdateService(config=config, pm=pm)

        result = service.apply()

        assert result.success is False
        assert result.error == "network error"
        # Flag NOT cleared on failure (attempt tracking deferred to 03-01)
        assert config.read_pending_update() is not None
