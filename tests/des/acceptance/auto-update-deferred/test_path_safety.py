"""PATH-safety acceptance scenario for ``PendingUpdateService.apply()``.

Spike C1 constraint: the absolute pm-binary path stored in the flag at
``/nw-update`` request time MUST be forwarded unchanged to the
``PackageManagerPort.upgrade()`` call. The adapter layer does NOT re-resolve
the binary from ``$PATH`` at session-start apply time -- this is essential
because the session-start hook can run under a reduced or empty PATH where
pipx/uv are not discoverable via ``shutil.which``.

Scenario (from distill):

- Upgrade succeeds when PM binary is only reachable via stored absolute path
  (system PATH does not contain pipx).
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


def test_apply_forwards_stored_abspath_when_pm_missing_from_path(
    des_config: DESConfig,
    fake_package_manager_factory: Callable[[], FakePackageManager],
    existing_pm_binary: Callable[[str], str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stored abspath forwarded verbatim even when PATH does not contain pipx."""
    # Given: a minimal PATH that does NOT contain pipx/uv
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    # And: a pending flag whose pm_binary_abspath exists on disk outside PATH
    pipx_path = existing_pm_binary("pipx")
    des_config.save_pending_update_state(
        PendingUpdateFlag(
            pm="pipx",
            pm_binary_abspath=pipx_path,
            target_version="3.12.0",
            requested_at=datetime.now(timezone.utc).isoformat(),
            attempt_count=0,
            last_error=None,
        )
    )

    pm = fake_package_manager_factory()
    pm.will_succeed()
    service = PendingUpdateService(config=des_config, pm=pm)

    # When: apply() runs at session start under the reduced PATH
    result = service.apply()

    # Then: the port receives the flag's stored abspath verbatim (no re-resolution)
    assert pm.calls == [(pipx_path, "3.12.0")]
    # And: success result, flag cleared
    assert result.success is True
    assert result.error is None
    assert des_config.read_pending_update() is None
