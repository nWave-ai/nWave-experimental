"""Observability acceptance tests for ``PendingUpdateService.apply()``.

Scenarios (from distill):

- Upgrade banner is emitted before the package manager subprocess is invoked
  (ordering: banner MUST appear on stderr prior to ``port.upgrade()`` call).
- Failure banner is emitted when the upgrade does not complete (content
  includes attempt count + last error + current version reassurance).

Strategy C: real temp-filesystem I/O; ``FakePackageManager`` at the
``PackageManagerPort`` boundary with a ``pre_call_hook`` that records whether
the start banner was emitted before ``upgrade()`` ran.
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

    from des.adapters.driven.config.des_config import DESConfig
    from des.adapters.driven.package_managers.fake_package_manager import (
        FakePackageManager,
    )


pytestmark = [pytest.mark.acceptance]


def _preexisting_flag(
    pm: str, binary: str, version: str, attempt_count: int = 0
) -> PendingUpdateFlag:
    return PendingUpdateFlag(
        pm=pm,
        pm_binary_abspath=binary,
        target_version=version,
        requested_at=datetime.now(timezone.utc).isoformat(),
        attempt_count=attempt_count,
        last_error=None,
    )


def test_upgrade_banner_emitted_before_package_manager_invoked(
    des_config: DESConfig,
    fake_package_manager_factory: Callable[[], FakePackageManager],
    existing_pm_binary: Callable[[str], str],
) -> None:
    """Start banner MUST be on stderr BEFORE ``port.upgrade()`` is called."""
    # Given: a pending pipx upgrade flag
    des_config.save_pending_update_state(
        _preexisting_flag("pipx", existing_pm_binary("pipx"), "3.12.0")
    )

    stderr_buf = io.StringIO()
    pm = fake_package_manager_factory()
    pm.will_succeed()

    # Spy: capture stderr snapshot at the moment upgrade() is invoked
    banner_seen_at_call_time: dict[str, str] = {}

    def _pre_call_hook() -> None:
        banner_seen_at_call_time["stderr"] = stderr_buf.getvalue()

    pm.pre_call_hook = _pre_call_hook

    service = PendingUpdateService(
        config=des_config,
        pm=pm,
        current_version="3.10.1",
        stderr=stderr_buf,
    )

    # When: apply() runs at session start
    result = service.apply()

    # Then: the start banner was already emitted BEFORE upgrade() ran
    assert "stderr" in banner_seen_at_call_time, "pre_call_hook did not fire"
    pre_upgrade_stderr = banner_seen_at_call_time["stderr"]
    assert "Updating nWave (3.10.1 \u2192 3.12.0)" in pre_upgrade_stderr
    assert "~30s" in pre_upgrade_stderr

    # And: success banner emitted after
    assert result.success is True
    final_stderr = stderr_buf.getvalue()
    assert "nWave updated. Session continuing." in final_stderr


def test_failure_banner_emitted_with_attempt_count_and_error(
    des_config: DESConfig,
    fake_package_manager_factory: Callable[[], FakePackageManager],
    existing_pm_binary: Callable[[str], str],
) -> None:
    """Failure banner content: attempt n/3, last_error, current_version."""
    # Given: a pending flag with no prior failures
    des_config.save_pending_update_state(
        _preexisting_flag("pipx", existing_pm_binary("pipx"), "3.12.0", attempt_count=0)
    )

    stderr_buf = io.StringIO()
    pm = fake_package_manager_factory()
    pm.will_fail("network timeout")

    service = PendingUpdateService(
        config=des_config,
        pm=pm,
        current_version="3.10.1",
        stderr=stderr_buf,
    )

    # When: apply() runs and the package manager fails
    result = service.apply()

    # Then: failure banner includes attempt count (1/3), error, current version
    assert result.success is False
    output = stderr_buf.getvalue()
    assert "Updating nWave (3.10.1 \u2192 3.12.0)" in output  # start banner
    assert "nWave update failed (attempt 1/3): network timeout" in output
    assert "Session continuing with 3.10.1." in output
