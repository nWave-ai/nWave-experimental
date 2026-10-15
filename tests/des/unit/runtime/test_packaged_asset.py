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


def _asset_message(what: str, how: str) -> str:
    return (
        f"WHAT: {what}. WHY: installed role assets must resolve by the requested "
        f"asset, not an unrelated nWave directory. HOW: {how}."
    )


def test_each_supported_layout_skips_nearer_unrelated_nwave_roots(
    tmp_path: Path, monkeypatch
) -> None:
    """Exercise the closed physical-layout inventory with real asset bytes."""
    from des.runtime.packaged_asset import AssetOrigin, resolve_packaged_asset

    layouts = {
        "claude": ("lib/python/des", "lib"),
        "host-neutral": ("runtime/des", ""),
        "nested-wheel": ("nWave/lib/python/des", ""),
        "checkout": ("src/des", ""),
    }
    relatives = (
        "nWave/templates/architect-handoff",
        "nWave/skills/nw-design",
        "nWave/agents/nw-solution-architect.md",
    )
    for name, (package, asset_root) in layouts.items():
        root = tmp_path / name
        package_dir = root / package
        package_dir.mkdir(parents=True)
        residue = package_dir.parent / "nWave" / "hooks"
        residue.mkdir(parents=True)
        (residue / "old-hook.py").write_text("# existing hooks residue\n")
        monkeypatch.setattr(des, "__path__", [str(package_dir)])
        start = root / "consumer"
        start.mkdir()
        for relative in relatives:
            expected = root / asset_root / relative
            if expected.suffix == ".md":
                expected.parent.mkdir(parents=True, exist_ok=True)
                expected.write_text("public role\n")
            else:
                expected.mkdir(parents=True, exist_ok=True)
                (expected / "asset.md").write_text("public asset\n")
            result = resolve_packaged_asset(relative, start=start)
            assert (result.origin, result.path, result.installed) == (
                AssetOrigin.INSTALLED,
                expected,
                expected,
            ), _asset_message(
                f"{name}/{relative} resolved to {result}, expected {expected}",
                "choose the nearest package ancestor containing the full relative "
                "asset path; skip the hooks-only ancestor",
            )
        assert (residue / "old-hook.py").read_text() == (
            "# existing hooks residue\n"
        ), _asset_message(
            "asset resolution changed the pre-existing hooks residue",
            "resolve without deleting or rewriting unrelated runtime assets",
        )


def test_nearest_containing_ancestor_wins_over_an_older_complete_tree(
    tmp_path: Path, monkeypatch
) -> None:
    from des.runtime.packaged_asset import AssetOrigin, resolve_packaged_asset

    package = tmp_path / "outer" / "runtime" / "python" / "des"
    package.mkdir(parents=True)
    relative = "nWave/agents/nw-solution-architect.md"
    near = package.parent / relative
    far = tmp_path / "outer" / relative
    for path, text in ((near, "near current role"), (far, "older role")):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    monkeypatch.setattr(des, "__path__", [str(package)])
    result = resolve_packaged_asset(relative, start=tmp_path)
    assert (result.origin, result.path) == (
        AssetOrigin.INSTALLED,
        near,
    ), _asset_message(
        f"nearest complete asset was {near}, actual resolution {result}",
        "stop at the first ancestor containing the requested asset",
    )


def test_asset_choice_preserves_explicit_identity_ambiguity_and_absence(
    tmp_path: Path, monkeypatch
) -> None:
    from des.runtime.packaged_asset import (
        AssetOrigin,
        ambiguity_message,
        resolve_packaged_asset,
    )

    package = tmp_path / "installation" / "python" / "des"
    package.mkdir(parents=True)
    monkeypatch.setattr(des, "__path__", [str(package)])
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / ".git").mkdir()
    relative = "nWave/templates/role.tmpl"
    derived = package.parent.parent / relative
    override = tmp_path / "explicit" / "role.tmpl"
    repo = checkout / relative
    for path in (derived, override, repo):
        path.parent.mkdir(parents=True, exist_ok=True)
    derived.write_text("derived asset")
    override.write_text("explicit asset")
    result = resolve_packaged_asset(relative, start=tmp_path, installed=override)
    assert (result.origin, result.path, result.installed) == (
        AssetOrigin.INSTALLED,
        override,
        override,
    ), _asset_message(
        f"explicit installed candidate was replaced: {result}",
        "honor installed= without deriving another candidate",
    )

    for equal in (True, False):
        repo.write_bytes(derived.read_bytes() if equal else b"different checkout")
        result = resolve_packaged_asset(relative, start=checkout)
        expected_origin = AssetOrigin.REPO if equal else AssetOrigin.AMBIGUOUS
        assert (result.origin, result.path, result.installed, result.repo) == (
            expected_origin,
            repo if equal else None,
            derived,
            repo,
        ), _asset_message(
            f"equal={equal} returned {result}",
            "compare the existing candidate digests; choose REPO only when equal "
            "and refuse ambiguity when the two trees differ",
        )
        if not equal:
            diagnostic = ambiguity_message(result, "--asset")
            assert all(
                token in diagnostic
                for token in ("WHAT", "WHY", "HOW", str(repo), str(derived))
            ), _asset_message(
                "ambiguity diagnostic lost its existing actionable candidates",
                "retain ambiguity_message and both exact candidate paths",
            )

    derived.unlink()
    repo.unlink()
    missing = resolve_packaged_asset(relative, start=checkout)
    diagnostic_candidate = installed_package_root() / relative
    assert (missing.origin, missing.path, missing.installed) == (
        AssetOrigin.ABSENT,
        None,
        diagnostic_candidate,
    ), _asset_message(
        f"absent asset returned {missing}, expected {diagnostic_candidate}",
        "keep installed_package_root()/relative as the absent diagnostic "
        "candidate rather than inventing a successful fallback",
    )
