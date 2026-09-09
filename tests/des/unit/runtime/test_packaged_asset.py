"""Asset roots must follow the actual wheel layout, not a fixed parent count."""

from __future__ import annotations

from pathlib import Path

import des
from des.runtime.packaged_asset import installed_package_root


def test_bundled_wheel_runtime_finds_assets_beside_the_nwave_container(
    tmp_path: Path, monkeypatch
) -> None:
    """A wheel stores DES in ``nWave/lib/python`` and assets in ``nWave/data``."""
    site_packages = tmp_path / "site-packages"
    des_dir = site_packages / "nWave" / "lib" / "python" / "des"
    des_dir.mkdir(parents=True)
    (site_packages / "nWave" / "data" / "brand").mkdir(parents=True)
    monkeypatch.setattr(des, "__path__", [str(des_dir)])

    assert installed_package_root() == site_packages
