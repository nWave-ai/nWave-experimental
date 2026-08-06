"""Unit tests for install-metadata recording.

``record_install_metadata`` writes the install provenance into the GLOBAL config
(``~/.nwave/global-config.json``):
  - ``install.installed_version`` — the package version that deployed the
    framework, the anchor the doctor VersionSyncCheck compares against the live
    ``importlib.metadata`` version to detect "upgraded but not reinstalled" drift.
Contract: read-modify-write (never clobbers unrelated keys) and best-effort
(never raises — an install must not fail because a metadata write failed).
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.install.install_nwave import record_install_metadata


def test_writes_installed_version(tmp_path: Path) -> None:
    cfg = tmp_path / ".nwave" / "global-config.json"

    record_install_metadata(cfg, installed_version="1.2.0")

    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert data["install"]["installed_version"] == "1.2.0"


def test_creates_parent_directory_when_absent(tmp_path: Path) -> None:
    cfg = tmp_path / "nested" / ".nwave" / "global-config.json"

    record_install_metadata(cfg, installed_version="2.0.0")

    assert cfg.exists()
    assert (
        json.loads(cfg.read_text(encoding="utf-8"))["install"]["installed_version"]
        == "2.0.0"
    )


def test_preserves_unrelated_existing_keys(tmp_path: Path) -> None:
    cfg = tmp_path / ".nwave" / "global-config.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        json.dumps(
            {
                "rigor": {"profile": "thorough"},
                "update_check": {"frequency": "weekly"},
                "install": {"user_owned_key": "uv"},
            }
        ),
        encoding="utf-8",
    )

    record_install_metadata(cfg, installed_version="3.0.0")

    data = json.loads(cfg.read_text(encoding="utf-8"))
    # Unrelated blocks untouched.
    assert data["rigor"] == {"profile": "thorough"}
    assert data["update_check"] == {"frequency": "weekly"}
    # install block updated, sibling install keys preserved.
    assert data["install"]["installed_version"] == "3.0.0"
    assert data["install"]["user_owned_key"] == "uv"


def test_best_effort_on_corrupt_existing_config(tmp_path: Path) -> None:
    """Corrupt existing JSON is overwritten with a fresh valid config, no raise."""
    cfg = tmp_path / ".nwave" / "global-config.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("{ not json", encoding="utf-8")

    record_install_metadata(cfg, installed_version="1.0.0")

    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert data["install"]["installed_version"] == "1.0.0"
