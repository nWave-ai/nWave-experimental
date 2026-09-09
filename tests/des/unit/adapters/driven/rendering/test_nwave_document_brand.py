"""The renderer owns one local packaged brand and never fetches a document asset."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.adapters.driven.rendering import nwave_document
from des.runtime.packaged_asset import AssetOrigin, AssetResolution


_MANIFEST = (
    '{"schema-version":1,"identity":"nwave-oss-neutral-v1",'
    '"stylesheet":"nwave.css",'
    '"font-stack":"ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif"}\n'
)


def test_page_identifies_the_versioned_local_brand_and_has_no_remote_url() -> None:
    page = nwave_document.build_page("# State", ".nwave/des/handover.json", "State")
    manifest_path = (
        Path(nwave_document.__file__).resolve().parents[5]
        / "nWave/data/brand/manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest_path.read_text(encoding="utf-8") == _MANIFEST
    assert f'name="nwave-brand" content="{manifest["identity"]}"' in page
    assert f"--nwave-font-stack:{manifest['font-stack']}" in page
    assert "--paper" in page
    assert ':root[data-theme="light"]' in page
    assert "ul.tree ul.tree>li::before" in page
    assert "prefers-reduced-motion:reduce" in page
    assert "default-src 'none'" in page
    assert "style-src 'unsafe-inline'" in page
    assert "img-src data:" in page
    assert "font-src data:" in page
    assert "connect-src 'none'" in page
    assert "http://" not in page
    assert "https://" not in page


def test_invalid_or_unavailable_brand_refuses(monkeypatch, tmp_path: Path) -> None:
    missing = tmp_path / "brand"
    resolution = AssetResolution(
        AssetOrigin.ABSENT,
        None,
        missing,
        None,
        "brand asset is absent",
    )
    monkeypatch.setattr(
        nwave_document, "resolve_packaged_asset", lambda _name: resolution
    )

    with pytest.raises(nwave_document.BrandAssetError, match="unavailable"):
        nwave_document.build_page("# State", ".nwave/des/handover.json", "State")


def test_manifest_font_stack_cannot_inject_a_second_style_rule(
    monkeypatch, tmp_path: Path
) -> None:
    """The manifest owns a CSS value, never an arbitrary style fragment."""
    brand_dir = tmp_path / "brand"
    brand_dir.mkdir()
    (brand_dir / "manifest.json").write_text(
        """{
  "schema-version": 1,
  "identity": "nwave-oss-neutral-v1",
  "stylesheet": "nwave.css",
  "font-stack": "sans-serif; background: url(https://example.invalid/x)"
}
""",
        encoding="utf-8",
    )
    (brand_dir / "nwave.css").write_text("body{}", encoding="utf-8")
    resolution = AssetResolution(
        AssetOrigin.REPO, brand_dir, brand_dir, brand_dir, "test brand"
    )
    monkeypatch.setattr(
        nwave_document, "resolve_packaged_asset", lambda _name: resolution
    )

    with pytest.raises(nwave_document.BrandAssetError, match="font-stack"):
        nwave_document.load_brand()
