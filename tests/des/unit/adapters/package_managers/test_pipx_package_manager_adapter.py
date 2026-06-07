"""Unit tests for PipxPackageManagerAdapter.

The adapter implements PackageManagerPort by invoking pipx in two phases:
  1. ``<pipx> upgrade nwave-ai`` - upgrades the package itself
  2. ``nwave-ai install`` - re-installs nWave framework assets from the new version

Unit tests mock ``subprocess.run`` at the module boundary; real subprocess
behavior is exercised in the Docker integration test (step 04-03).
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from des.adapters.driven.package_managers.pipx_package_manager_adapter import (
    PipxPackageManagerAdapter,
)
from des.ports.driven_ports.package_manager_port import (
    PackageManagerPort,
    UpgradeResult,
)


PIPX = "/home/user/.local/bin/pipx"
NWAVE_AI = "/home/user/.local/bin/nwave-ai"
VERSION = "1.2.3"


def _ok(stdout: str = "", stderr: str = "") -> MagicMock:
    result = MagicMock()
    result.returncode = 0
    result.stdout = stdout
    result.stderr = stderr
    return result


def _fail(stderr: str, returncode: int = 1) -> MagicMock:
    result = MagicMock()
    result.returncode = returncode
    result.stdout = ""
    result.stderr = stderr
    return result


class TestPipxPackageManagerAdapter:
    def test_implements_package_manager_port(self) -> None:
        adapter = PipxPackageManagerAdapter()
        assert isinstance(adapter, PackageManagerPort)

    @patch(
        "des.adapters.driven.package_managers."
        "pipx_package_manager_adapter.shutil.which",
        return_value=NWAVE_AI,
    )
    @patch(
        "des.adapters.driven.package_managers."
        "pipx_package_manager_adapter.subprocess.run"
    )
    def test_successful_upgrade_and_install_returns_success(
        self, mock_run: MagicMock, _mock_which: MagicMock
    ) -> None:
        mock_run.side_effect = [_ok("upgraded"), _ok("installed")]
        adapter = PipxPackageManagerAdapter()

        result = adapter.upgrade(PIPX, VERSION)

        assert result == UpgradeResult(success=True, error=None)
        assert mock_run.call_count == 2
        # First call: pipx upgrade nwave-ai
        first_cmd = mock_run.call_args_list[0].args[0]
        assert first_cmd == [PIPX, "upgrade", "nwave-ai"]
        # Second call: nwave-ai install
        second_cmd = mock_run.call_args_list[1].args[0]
        assert second_cmd == [NWAVE_AI, "install"]

    @patch(
        "des.adapters.driven.package_managers."
        "pipx_package_manager_adapter.subprocess.run"
    )
    def test_pm_upgrade_failure_returns_phase_pm_upgrade(
        self, mock_run: MagicMock
    ) -> None:
        mock_run.return_value = _fail("pipx: network error")
        adapter = PipxPackageManagerAdapter()

        result = adapter.upgrade(PIPX, VERSION)

        assert result.success is False
        assert "pipx: network error" in (result.error or "")
        assert result.phase == "pm_upgrade"
        assert mock_run.call_count == 1  # second phase not attempted

    @patch(
        "des.adapters.driven.package_managers."
        "pipx_package_manager_adapter.shutil.which",
        return_value=NWAVE_AI,
    )
    @patch(
        "des.adapters.driven.package_managers."
        "pipx_package_manager_adapter.subprocess.run"
    )
    def test_nwave_install_failure_returns_phase_nwave_install(
        self, mock_run: MagicMock, _mock_which: MagicMock
    ) -> None:
        mock_run.side_effect = [_ok("upgraded"), _fail("install failed")]
        adapter = PipxPackageManagerAdapter()

        result = adapter.upgrade(PIPX, VERSION)

        assert result.success is False
        assert "install failed" in (result.error or "")
        assert result.phase == "nwave_install"

    @patch(
        "des.adapters.driven.package_managers."
        "pipx_package_manager_adapter.subprocess.run"
    )
    def test_timeout_during_upgrade_returns_graceful_failure(
        self, mock_run: MagicMock
    ) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=PIPX, timeout=120)
        adapter = PipxPackageManagerAdapter()

        result = adapter.upgrade(PIPX, VERSION)

        assert result.success is False
        assert result.phase == "pm_upgrade"
        assert "timeout" in (result.error or "").lower()

    @patch(
        "des.adapters.driven.package_managers."
        "pipx_package_manager_adapter.subprocess.run"
    )
    def test_binary_not_found_returns_graceful_failure(
        self, mock_run: MagicMock
    ) -> None:
        mock_run.side_effect = FileNotFoundError(2, "No such file", PIPX)
        adapter = PipxPackageManagerAdapter()

        result = adapter.upgrade(PIPX, VERSION)

        assert result.success is False
        assert result.phase == "pm_upgrade"
        assert "binary not found" in (result.error or "").lower()
        assert PIPX in (result.error or "")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
