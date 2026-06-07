"""Error-path acceptance tests for auto-update-deferred (step 03-04).

Covers error branches in ``PendingUpdateService.apply()`` beyond the attempt-cap
trajectory:

- Network failure (pipx): flag retained, attempt_count incremented, last_error set.
- Network failure (uv): same behavior for the uv package manager variant.
- Binary not found: ``apply()`` does NOT invoke the package manager port; it
  increments attempts and persists a "binary not found" last_error.
- Unknown pm in flag: ``apply()`` skips the upgrade, emits a warning banner,
  does NOT invoke the package manager, and persists last_error without
  incrementing attempt_count.

Strategy C: real temp-filesystem I/O, FakePackageManager at the
PackageManagerPort boundary. Enters through the ``PendingUpdateService``
driving port only.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest

from des.application.pending_update_service import PendingUpdateService
from des.domain.pending_update_flag import PendingUpdateFlag


if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from des.adapters.driven.config.des_config import DESConfig
    from des.adapters.driven.package_managers.fake_package_manager import (
        FakePackageManager,
    )


pytestmark = [pytest.mark.acceptance]


def _make_flag(
    *,
    pm: str = "pipx",
    pm_binary_abspath: str = "/usr/local/bin/pipx",
    target_version: str = "3.11.0",
    attempt_count: int = 0,
    last_error: str | None = None,
) -> PendingUpdateFlag:
    return PendingUpdateFlag(
        pm=pm,  # type: ignore[arg-type]
        pm_binary_abspath=pm_binary_abspath,
        target_version=target_version,
        requested_at=datetime.now(timezone.utc).isoformat(),
        attempt_count=attempt_count,
        last_error=last_error,
    )


def test_pipx_network_failure_retains_flag_with_incremented_attempt_count(
    tmp_nwave_home: Path,
    des_config: DESConfig,
    fake_package_manager_factory: Callable[[], FakePackageManager],
) -> None:
    """Scenario: Network failure during apply leaves the flag with
    incremented attempt count (pipx)."""
    pipx_bin = tmp_nwave_home / "bin" / "pipx"
    pipx_bin.parent.mkdir(parents=True, exist_ok=True)
    pipx_bin.write_text("#!/bin/sh\n")
    des_config.save_pending_update_state(
        _make_flag(pm="pipx", pm_binary_abspath=str(pipx_bin), attempt_count=0)
    )

    pm = fake_package_manager_factory()
    pm.will_fail("network error")
    service = PendingUpdateService(config=des_config, pm=pm)

    result = service.apply()

    assert result.success is False
    assert result.error == "network error"

    persisted = des_config.read_pending_update()
    assert persisted is not None
    assert persisted.attempt_count == 1
    assert persisted.last_error == "network error"


def test_uv_network_failure_retains_flag_with_incremented_attempt_count(
    tmp_nwave_home: Path,
    des_config: DESConfig,
    fake_package_manager_factory: Callable[[], FakePackageManager],
) -> None:
    """Scenario: Network failure during uv apply leaves the flag with
    incremented attempt count (starting from count=1 -> count=2)."""
    uv_bin = tmp_nwave_home / "bin" / "uv"
    uv_bin.parent.mkdir(parents=True, exist_ok=True)
    uv_bin.write_text("#!/bin/sh\n")
    des_config.save_pending_update_state(
        _make_flag(
            pm="uv",
            pm_binary_abspath=str(uv_bin),
            attempt_count=1,
            last_error="prior network error",
        )
    )

    pm = fake_package_manager_factory()
    pm.will_fail("network error")
    service = PendingUpdateService(config=des_config, pm=pm)

    result = service.apply()

    assert result.success is False
    assert result.error == "network error"

    persisted = des_config.read_pending_update()
    assert persisted is not None
    assert persisted.pm == "uv"
    assert persisted.attempt_count == 2
    assert persisted.last_error == "network error"


def test_binary_not_found_skips_port_and_records_error(
    tmp_nwave_home: Path,
    des_config: DESConfig,
    fake_package_manager_factory: Callable[[], FakePackageManager],
) -> None:
    """Scenario: Binary not found error leaves the flag retained with clear
    error message and does NOT invoke the package manager port."""
    missing = str(tmp_nwave_home / "nonexistent" / "pipx")
    des_config.save_pending_update_state(
        _make_flag(pm="pipx", pm_binary_abspath=missing, attempt_count=0)
    )

    pm = fake_package_manager_factory()
    # Do NOT program the fake: if apply() calls it, the assert inside
    # FakePackageManager.upgrade() will fail loudly.
    service = PendingUpdateService(config=des_config, pm=pm)

    result = service.apply()

    assert len(pm.calls) == 0, (
        "apply() must NOT invoke the package manager when the pm binary is "
        "missing on disk"
    )
    assert result.success is False
    assert result.error is not None
    assert "binary not found" in result.error.lower()
    assert missing in result.error

    persisted = des_config.read_pending_update()
    assert persisted is not None
    assert persisted.attempt_count == 1
    assert persisted.last_error is not None
    assert "binary not found" in persisted.last_error.lower()


def test_unknown_pm_skips_upgrade_emits_warning_and_preserves_attempt_count(
    des_config: DESConfig,
    fake_package_manager_factory: Callable[[], FakePackageManager],
) -> None:
    """Scenario: Unknown PM in flag skips upgrade and emits warning banner.

    The flag is NOT dropped immediately (caller may wish to inspect it), but
    last_error is persisted. attempt_count is NOT incremented because no
    upgrade attempt was made.
    """
    des_config.save_pending_update_state(
        _make_flag(
            pm="unknown",
            pm_binary_abspath="/opt/mystery-pm",
            attempt_count=0,
        )
    )

    pm = fake_package_manager_factory()
    stderr = io.StringIO()
    service = PendingUpdateService(config=des_config, pm=pm, stderr=stderr)

    result = service.apply()

    assert len(pm.calls) == 0, (
        "apply() must NOT invoke the package manager when pm=='unknown'"
    )
    assert result.success is False
    assert result.error is not None
    assert "unknown" in result.error.lower()

    banner = stderr.getvalue()
    assert "cannot apply update" in banner.lower()
    assert "unknown" in banner.lower()
    assert "nwave-ai install" in banner.lower()

    persisted = des_config.read_pending_update()
    assert persisted is not None, "unknown-pm flag must not be dropped immediately"
    assert persisted.attempt_count == 0, (
        "attempt_count must NOT be incremented when no upgrade was attempted"
    )
    assert persisted.last_error is not None
    assert "unknown" in persisted.last_error.lower()


def test_invalid_target_version_retains_flag_with_incremented_attempt_count(
    tmp_nwave_home: Path,
    des_config: DESConfig,
    fake_package_manager_factory: Callable[[], FakePackageManager],
) -> None:
    """Scenario: Package manager reports target version unavailable on the registry.

    When pipx reports "version 99.99.99 not found on PyPI", the flag is retained
    with this last_error and attempt_count is incremented so the next session can
    either retry (if user corrected the target) or cap out.
    """
    pipx_bin = tmp_nwave_home / "bin" / "pipx"
    pipx_bin.parent.mkdir(parents=True, exist_ok=True)
    pipx_bin.write_text("#!/bin/sh\n")
    des_config.save_pending_update_state(
        _make_flag(
            pm="pipx",
            pm_binary_abspath=str(pipx_bin),
            target_version="99.99.99",
            attempt_count=0,
        )
    )

    pm = fake_package_manager_factory()
    pm.will_fail("target version 99.99.99 not found on PyPI")
    service = PendingUpdateService(config=des_config, pm=pm)

    result = service.apply()

    assert result.success is False
    assert result.error is not None
    assert "99.99.99 not found" in result.error

    persisted = des_config.read_pending_update()
    assert persisted is not None
    assert persisted.attempt_count == 1
    assert persisted.last_error is not None
    assert "99.99.99 not found" in persisted.last_error


def test_nwave_install_phase_failure_retains_flag_with_phase_in_last_error(
    tmp_nwave_home: Path,
    des_config: DESConfig,
    fake_package_manager_factory: Callable[[], FakePackageManager],
) -> None:
    """Scenario: PM upgrade succeeds but nwave-ai install step fails; flag retained.

    Two-phase upgrade model: (1) pipx upgrade succeeds, (2) nwave-ai install
    fails. The flag is retained with a last_error that identifies the phase
    (prefixed with ``[nwave_install]``) so the next-session retry can pick the
    right recovery path.
    """
    pipx_bin = tmp_nwave_home / "bin" / "pipx"
    pipx_bin.parent.mkdir(parents=True, exist_ok=True)
    pipx_bin.write_text("#!/bin/sh\n")
    des_config.save_pending_update_state(
        _make_flag(pm="pipx", pm_binary_abspath=str(pipx_bin), attempt_count=0)
    )

    pm = fake_package_manager_factory()
    pm.will_fail_in_phase("nwave_install", "post-upgrade install script crashed")
    service = PendingUpdateService(config=des_config, pm=pm)

    result = service.apply()

    assert result.success is False
    assert result.phase == "nwave_install"
    assert result.error is not None
    assert "post-upgrade install script crashed" in result.error

    persisted = des_config.read_pending_update()
    assert persisted is not None
    assert persisted.attempt_count == 1
    assert persisted.last_error is not None
    assert persisted.last_error.startswith("[nwave_install]")
    assert "post-upgrade install script crashed" in persisted.last_error
