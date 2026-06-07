"""Happy-path acceptance tests for ``PendingUpdateService.request_update``.

Strategy C: real temp-filesystem I/O for the flag file. Tests enter through
the ``PendingUpdateService`` driving port and assert observable flag content
written to ``DESConfig.pending_update_path``.

Scenarios (from distill/acceptance-scenarios.md):

- Developer requests update and flag is written with pipx package manager
  details.
- Developer requests update and flag is written with uv package manager
  details.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path as _Path
from typing import TYPE_CHECKING

import pytest

from des.application.pending_update_service import PendingUpdateService


if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from des.adapters.driven.config.des_config import DESConfig
    from des.adapters.driven.package_managers.fake_package_manager import (
        FakePackageManager,
    )


pytestmark = [pytest.mark.acceptance]


@pytest.mark.parametrize(
    ("pm_name", "pm_binary_abspath"),
    [
        ("pipx", "/home/user/.local/share/pipx/venvs/nwave-ai/bin/python"),
        ("uv", "/home/user/.local/share/uv/tools/nwave-ai/bin/python"),
    ],
    ids=["pipx", "uv"],
)
def test_request_update_writes_flag_with_package_manager_details(
    des_config: DESConfig,
    tmp_nwave_home: Path,
    fake_package_manager_factory: Callable[[], FakePackageManager],
    pm_name: str,
    pm_binary_abspath: str,
) -> None:
    """request_update persists a flag whose content matches the inputs.

    Given: no pending update flag exists.
    When:  developer requests an update for ``pm_name`` with a resolved
           absolute binary path and a target version.
    Then:  the flag file exists at ``DESConfig.pending_update_path`` and
           records pm, pm_binary_abspath, target_version, attempt_count=0,
           last_error=None, and an ISO-8601 requested_at timestamp.
    """
    # Given: no pending update flag exists
    assert des_config.read_pending_update() is None

    # request_update does not touch the package manager, but the service
    # contract types pm as non-None — supply the fake at the port boundary.
    service = PendingUpdateService(config=des_config, pm=fake_package_manager_factory())

    # When: developer requests an update
    service.request_update(
        pm=pm_name,
        pm_binary_abspath=pm_binary_abspath,
        target_version="3.11.0",
    )

    # Then: flag is persisted at the expected location with matching content
    assert des_config.pending_update_path.exists(), (
        "flag file must be written at DESConfig.pending_update_path"
    )
    flag = des_config.read_pending_update()
    assert flag is not None
    assert flag.pm == pm_name
    assert flag.pm_binary_abspath == pm_binary_abspath
    # And: binary path is absolute
    assert _Path(flag.pm_binary_abspath).is_absolute()
    assert flag.target_version == "3.11.0"
    assert flag.attempt_count == 0
    assert flag.last_error is None
    # And: requested_at is ISO-8601 parseable
    parsed = datetime.fromisoformat(flag.requested_at)
    assert parsed is not None
