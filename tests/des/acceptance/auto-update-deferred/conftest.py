"""Fixtures for auto-update-deferred acceptance tests.

Provides real-filesystem isolation via ``tmp_path`` (Strategy C), a fresh
``DESConfig`` pointed at that temp home, and a session-scoped factory for the
``FakePackageManager`` test double at the ``PackageManagerPort`` boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from des.adapters.driven.config.des_config import DESConfig
from des.adapters.driven.package_managers.fake_package_manager import (
    FakePackageManager,
)


if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path
else:
    from pathlib import Path


@pytest.fixture
def tmp_nwave_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Redirect ``Path.home()`` to a real temp dir so ``pending_update_path``
    resolves inside ``tmp_path/.nwave/``. Function-scoped for isolation."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    yield tmp_path


@pytest.fixture
def des_config(tmp_nwave_home: Path) -> DESConfig:
    """Fresh DESConfig whose pending_update_path lives under tmp_nwave_home."""
    return DESConfig(config_path=tmp_nwave_home / ".nwave" / "des-config.json")


@pytest.fixture
def fake_package_manager_factory() -> Callable[[], FakePackageManager]:
    """Factory for programmable FakePackageManager instances."""
    return FakePackageManager


@pytest.fixture
def existing_pm_binary(tmp_nwave_home: Path) -> Callable[[str], str]:
    """Factory for a real on-disk fake pm binary under tmp_nwave_home.

    Returns the absolute path as str. Required because
    ``PendingUpdateService.apply()`` now rejects flags whose
    ``pm_binary_abspath`` does not exist on disk.
    """

    def _make(name: str = "pipx") -> str:
        binary = tmp_nwave_home / "bin" / name
        binary.parent.mkdir(parents=True, exist_ok=True)
        binary.write_text("#!/bin/sh\n")
        return str(binary)

    return _make
