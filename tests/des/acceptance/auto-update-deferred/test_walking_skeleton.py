"""Walking Skeleton acceptance tests for auto-update-deferred.

Strategy C: real temp-filesystem I/O for the flag file, ``FakePackageManager``
at the ``PackageManagerPort`` boundary. Tests enter through the
``PendingUpdateService`` driving port end-to-end.

Scenarios (from distill/walking-skeleton.md):

- WS1: Developer schedules update via pipx and nWave applies it at next session
  start.
- WS2: nWave retries a failed upgrade up to 3 times before asking for manual
  action.
"""

from __future__ import annotations

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


pytestmark = [pytest.mark.acceptance, pytest.mark.walking_skeleton]


# --- WS1 --------------------------------------------------------------------


def test_ws1_schedule_update_and_apply_at_next_session(
    des_config: DESConfig,
    fake_package_manager_factory: Callable[[], FakePackageManager],
    tmp_nwave_home: Path,
    existing_pm_binary: Callable[[str], str],
) -> None:
    """WS1: /nw-update schedules a flag; next session applies it successfully.

    Given: no pending update flag exists.
    When:  developer requests update via pipx (request_update).
    Then:  flag is persisted with pipx details.
    When:  next session starts and apply() runs with a succeeding PM.
    Then:  upgrade is invoked with stored binary + target; flag is cleared;
           result.success is True.
    """
    # Given: no flag
    assert des_config.read_pending_update() is None

    pipx_path = existing_pm_binary("pipx")
    pm = fake_package_manager_factory()
    service = PendingUpdateService(config=des_config, pm=pm)

    # When: /nw-update is invoked
    service.request_update(
        pm="pipx",
        pm_binary_abspath=pipx_path,
        target_version="3.11.0",
    )

    # Then: flag is persisted with pipx details
    flag = des_config.read_pending_update()
    assert flag is not None
    assert flag.pm == "pipx"
    assert flag.pm_binary_abspath == pipx_path
    assert flag.target_version == "3.11.0"
    assert flag.attempt_count == 0

    # When: next session runs apply() with a succeeding package manager
    pm.will_succeed()
    result = service.apply()

    # Then: upgrade was invoked with stored binary + target version
    assert pm.calls == [(pipx_path, "3.11.0")]
    # And: result is success, flag is cleared
    assert result.success is True
    assert result.error is None
    assert des_config.read_pending_update() is None


# --- WS2 --------------------------------------------------------------------


def test_ws2_failed_upgrade_retried_up_to_three_times(
    des_config: DESConfig,
    fake_package_manager_factory: Callable[[], FakePackageManager],
    existing_pm_binary: Callable[[str], str],
) -> None:
    """WS2: attempt cap drops the flag after 3 consecutive failures.

    Given: flag exists with attempt_count=2, last_error set.
    When:  apply() runs with a failing PM.
    Then:  result.success is False; flag retained with attempt_count=3.
    When:  next session runs apply() again (flag now at cap).
    Then:  no upgrade is attempted; flag is removed; result carries a
           manual-intervention message.
    """
    pipx_path = existing_pm_binary("pipx")
    # Given: preexisting flag with 2 prior failures
    preexisting = PendingUpdateFlag(
        pm="pipx",
        pm_binary_abspath=pipx_path,
        target_version="3.11.0",
        requested_at=datetime.now(timezone.utc).isoformat(),
        attempt_count=2,
        last_error="earlier network error",
    )
    des_config.save_pending_update_state(preexisting)

    pm = fake_package_manager_factory()
    service = PendingUpdateService(config=des_config, pm=pm)

    # When: apply() runs with a failing PM
    pm.will_fail("network error: connection refused")
    result = service.apply()

    # Then: failure surfaced, flag retained with attempt_count=3
    assert result.success is False
    assert result.error is not None
    assert "network error" in result.error
    flag = des_config.read_pending_update()
    assert flag is not None
    assert flag.attempt_count == 3
    assert flag.last_error is not None
    assert "network error" in flag.last_error

    # When: next session applies again with flag at cap
    pre_apply_calls = len(pm.calls)
    result2 = service.apply()

    # Then: no upgrade attempted; flag dropped; manual intervention surfaced
    assert len(pm.calls) == pre_apply_calls, (
        "apply() must not invoke the package manager once the attempt cap "
        "has been reached"
    )
    assert des_config.read_pending_update() is None
    assert result2.success is False
    assert result2.error is not None
    manual_msg = result2.error.lower()
    assert "manual" in manual_msg or "re-run" in manual_msg or "rerun" in manual_msg
