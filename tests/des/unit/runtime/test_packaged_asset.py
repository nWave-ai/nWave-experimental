"""Installed-layout regression tests for packaged runtime assets."""

from __future__ import annotations

from pathlib import Path

import des
from des.runtime.packaged_asset import AssetOrigin, resolve_packaged_asset


def _wheel_layout(tmp_path: Path) -> tuple[Path, Path]:
    site_packages = tmp_path / "venv/lib/python3.12/site-packages"
    package_dir = site_packages / "des"
    package_dir.mkdir(parents=True)
    template = site_packages / "nWave/templates/expectation-charter.md"
    template.parent.mkdir(parents=True)
    template.write_text("installed template\n", encoding="utf-8")
    return package_dir, template


def test_resolver_finds_asset_adjacent_to_installed_des_package(
    tmp_path: Path, monkeypatch
) -> None:
    package_dir, template = _wheel_layout(tmp_path)
    target_repo = tmp_path / "target-repo"
    target_repo.mkdir()
    monkeypatch.setattr(des, "__path__", [str(package_dir)])

    resolution = resolve_packaged_asset(
        "nWave/templates/expectation-charter.md", start=target_repo
    )

    assert resolution.origin is AssetOrigin.INSTALLED
    assert resolution.path == template
