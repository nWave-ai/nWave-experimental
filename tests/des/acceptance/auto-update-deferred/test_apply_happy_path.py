"""Happy-path acceptance tests for ``PendingUpdateService.apply()``.

Strategy C: real temp-filesystem I/O for the flag file, ``FakePackageManager``
at the ``PackageManagerPort`` boundary. Tests enter through the
``PendingUpdateService`` driving port.

Scenarios (from distill):

- Session start applies pending pipx upgrade and clears the flag on success.
- Session start applies pending uv upgrade and clears the flag on success.
- Session start with no pending flag present returns no-update result.

Note: the uv ``@latest`` strategy is enforced by ``UvPackageManagerAdapter``
(Phase 4, step 04-02). At the service layer we only call
``port.upgrade(abspath, version)``; the ``FakePackageManager`` records the raw
args. The ``@latest`` assertion defers to the Phase 4 integration test.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest

from des.application.pending_update_service import PendingUpdateService
from des.domain.pending_update_flag import PendingUpdateFlag


if TYPE_CHECKING:
    from collections.abc import Callable

    from des.adapters.driven.config.des_config import DESConfig
    from des.adapters.driven.package_managers.fake_package_manager import (
        FakePackageManager,
    )


pytestmark = [pytest.mark.acceptance]


def _preexisting_flag(pm: str, binary: str, version: str) -> PendingUpdateFlag:
    return PendingUpdateFlag(
        pm=pm,
        pm_binary_abspath=binary,
        target_version=version,
        requested_at=datetime.now(timezone.utc).isoformat(),
        attempt_count=0,
        last_error=None,
    )


def test_apply_pipx_pending_upgrade_clears_flag_on_success(
    des_config: DESConfig,
    fake_package_manager_factory: Callable[[], FakePackageManager],
    existing_pm_binary: Callable[[str], str],
) -> None:
    """Pipx flag present + succeeding PM -> flag cleared, success result."""
    pipx_path = existing_pm_binary("pipx")
    # Given: a pending pipx upgrade flag
    des_config.save_pending_update_state(_preexisting_flag("pipx", pipx_path, "3.12.0"))

    pm = fake_package_manager_factory()
    pm.will_succeed()
    service = PendingUpdateService(config=des_config, pm=pm)

    # When: apply() runs at session start
    result = service.apply()

    # Then: upgrade invoked with stored binary + version
    assert pm.calls == [(pipx_path, "3.12.0")]
    # And: success result, flag cleared
    assert result.success is True
    assert result.error is None
    assert des_config.read_pending_update() is None


def test_apply_uv_pending_upgrade_clears_flag_on_success(
    des_config: DESConfig,
    fake_package_manager_factory: Callable[[], FakePackageManager],
    existing_pm_binary: Callable[[str], str],
) -> None:
    """Uv flag present + succeeding PM -> flag cleared, success result.

    The ``@latest`` strategy is an adapter-layer concern (Phase 4, step 04-02).
    At the service boundary, we only assert that the stored binary + version
    are forwarded to the port.
    """
    uv_path = existing_pm_binary("uv")
    # Given: a pending uv upgrade flag
    des_config.save_pending_update_state(_preexisting_flag("uv", uv_path, "0.5.0"))

    pm = fake_package_manager_factory()
    pm.will_succeed()
    service = PendingUpdateService(config=des_config, pm=pm)

    # When: apply() runs at session start
    result = service.apply()

    # Then: upgrade invoked with stored binary + version
    assert pm.calls == [(uv_path, "0.5.0")]
    # And: success result, flag cleared
    assert result.success is True
    assert result.error is None
    assert des_config.read_pending_update() is None


def test_apply_with_no_pending_flag_returns_no_update_result(
    des_config: DESConfig,
    fake_package_manager_factory: Callable[[], FakePackageManager],
) -> None:
    """No flag present -> success result, PM never invoked."""
    # Given: no pending update flag
    assert des_config.read_pending_update() is None

    pm = fake_package_manager_factory()
    service = PendingUpdateService(config=des_config, pm=pm)

    # When: apply() runs at session start
    result = service.apply()

    # Then: success result, no error
    assert result.success is True
    assert result.error is None
    # And: package manager was never invoked
    assert pm.calls == []
    # And: no flag created
    assert des_config.read_pending_update() is None
