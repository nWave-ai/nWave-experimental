"""Integration tests: flag file real-I/O round-trip and atomic removal.

Real filesystem (``tmp_path``) for flag I/O via ``DESConfig``; FakePackageManager
at the ``PackageManagerPort`` boundary (no subprocess, no network). The
``@integration`` marker is auto-applied by ``tests/conftest.py`` based on the
directory path (``tests/des/integration/``).

Scenarios (from distill, tags @real-io @adapter-integration):

- Flag written to real temp filesystem round-trips correctly via DESConfig.
- Flag removed atomically after successful apply with FakePackageManager.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from des.adapters.driven.config.des_config import DESConfig
from des.adapters.driven.package_managers.fake_package_manager import (
    FakePackageManager,
)
from des.application.pending_update_service import PendingUpdateService
from des.domain.pending_update_flag import PendingUpdateFlag


@pytest.fixture
def tmp_nwave_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect ``Path.home()`` to ``tmp_path`` so pending_update_path resolves
    to a real file under the test's temporary directory."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


@pytest.fixture
def des_config(tmp_nwave_home: Path) -> DESConfig:
    return DESConfig(config_path=tmp_nwave_home / ".nwave" / "des-config.json")


def _flag(pm: str, binary: str, version: str) -> PendingUpdateFlag:
    return PendingUpdateFlag(
        pm=pm,
        pm_binary_abspath=binary,
        target_version=version,
        requested_at=datetime.now(timezone.utc).isoformat(),
        attempt_count=0,
        last_error=None,
    )


def test_flag_round_trips_through_real_filesystem(
    des_config: DESConfig, tmp_nwave_home: Path
) -> None:
    """save_pending_update_state -> read_pending_update returns equal flag,
    backed by a real JSON file on the filesystem."""
    binary = str(tmp_nwave_home / "bin" / "pipx")
    original = _flag("pipx", binary, "3.12.0")

    des_config.save_pending_update_state(original)

    # File exists on the real filesystem at the expected path.
    assert des_config.pending_update_path.exists()
    assert des_config.pending_update_path.is_file()

    # Round-trip reconstruction matches the stored flag field-for-field.
    loaded = des_config.read_pending_update()
    assert loaded is not None
    assert loaded.pm == original.pm
    assert loaded.pm_binary_abspath == original.pm_binary_abspath
    assert loaded.target_version == original.target_version
    assert loaded.requested_at == original.requested_at
    assert loaded.attempt_count == original.attempt_count
    assert loaded.last_error == original.last_error


def test_flag_removed_atomically_after_successful_apply(
    des_config: DESConfig, tmp_nwave_home: Path
) -> None:
    """apply() with succeeding FakePackageManager removes the flag file from
    the real filesystem."""
    pipx_path = tmp_nwave_home / "bin" / "pipx"
    pipx_path.parent.mkdir(parents=True, exist_ok=True)
    pipx_path.write_text("#!/bin/sh\n")

    des_config.save_pending_update_state(_flag("pipx", str(pipx_path), "3.12.0"))
    assert des_config.pending_update_path.exists()

    pm = FakePackageManager()
    pm.will_succeed()
    service = PendingUpdateService(config=des_config, pm=pm)

    result = service.apply()

    assert result.success is True
    assert result.error is None
    # Flag file removed from the real filesystem.
    assert not des_config.pending_update_path.exists()
    assert des_config.read_pending_update() is None
