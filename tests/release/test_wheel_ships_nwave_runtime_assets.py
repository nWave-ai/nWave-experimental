"""Regression AT: the PyPI wheel force-include ships nWave RUNTIME ASSET CONTENT,
not just the des CODE.

Charter: docs/product/expectations/wheel-ships-nwave-runtime-assets/
         pypi-wheel-carries-the-runtime-content.md
Feature-delta: docs/feature/wheel-ships-nwave-runtime-assets/feature-delta.md

RCA (confirmed from source): `_patch_wheel_packages` (scripts/release/
patch_pyproject.py) builds the wheel `[tool.hatch.build.targets.wheel.
force-include]` map. On a pipx install, `install_nwave.py` sets
`framework_source = site-packages/nWave/`; `DESPlugin._install_nwave_runtime_assets`
(scripts/install/plugins/des_plugin.py) then reads
`framework_source / "nWave" / <name>` for each name in `_NWAVE_RUNTIME_ASSET_DIRS`
("flavors", "data", "templates", "schemas") + `_NWAVE_RUNTIME_ASSET_FILES`
("framework-catalog.yaml"). The current force-include map has NO entry at all
for "flavors"/"data", and its "nWave/templates" / "schemas" entries target
destinations one level short of the "nWave/nWave/<name>" prefix the pipx
resolution requires -- so on a PyPI install every one of these assets is
unresolvable and the whole methodology runtime (including
nWave/data/orchestrator-affordance/, the SessionStart affordance content) is
inert, even though the des CODE installed fine.

This AT is OUTCOME-anchored, not a string-match on the map: it runs the REAL
`patch_pyproject` on a sample pyproject.toml, parses the resulting
force-include map, materialises it as a throwaway fake pipx `site-packages/`
tree (copying the REAL repo content at each LHS into its RHS destination), then
drives the REAL `DESPlugin._install_nwave_runtime_assets` resolver against that
simulated layout -- exactly as a pipx install would -- and asserts on what
actually lands in `<claude_dir>/lib/nWave/`.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.des_plugin import DESPlugin
from scripts.release.patch_pyproject import patch_pyproject


if sys.version_info >= (3, 11):
    import tomllib as tomli
else:
    import tomli


# repo root: tests/release/test_wheel_ships_nwave_runtime_assets.py -> tests/release
# -> tests -> <repo root>
REPO_ROOT = Path(__file__).resolve().parents[2]

# Single source of truth for the required runtime-asset set -- read from the
# des_plugin constants, never hand-duplicated, so a future addition to either
# tuple is covered by construction (charter expectation #3).
REQUIRED_ASSET_DIRS = DESPlugin._NWAVE_RUNTIME_ASSET_DIRS
REQUIRED_ASSET_FILES = DESPlugin._NWAVE_RUNTIME_ASSET_FILES


# ---------------------------------------------------------------------------
# Shared materialisation helpers (one function per step, reused by every
# scenario below -- see nw-distill Mandate 12 / SSOT-via-services).
# ---------------------------------------------------------------------------


@pytest.fixture()
def patched_force_include_map(sample_pyproject_path, tmp_path) -> dict[str, str]:
    """Run the REAL `patch_pyproject` and parse the resulting force-include map.

    Drives the actual production wheel-config builder (not stubbed); this
    fixture only parses its TOML output back into a dict for assertions.
    """
    output_path = str(tmp_path / "patched_pyproject.toml")
    patch_pyproject(
        input_path=sample_pyproject_path,
        output_path=output_path,
        target_name="nwave-ai",
        target_version="1.1.22",
    )
    parsed = tomli.loads(Path(output_path).read_text(encoding="utf-8"))
    return (
        parsed.get("tool", {})
        .get("hatch", {})
        .get("build", {})
        .get("targets", {})
        .get("wheel", {})
        .get("force-include", {})
    )


def _materialize_wheel_tree(
    force_include: dict[str, str], fake_site_packages: Path
) -> None:
    """Materialise the patched force-include map as a fake pipx site-packages tree.

    For each LHS (repo-relative source) -> RHS (wheel destination) pair, copies
    the REAL repo content at LHS into fake_site_packages/RHS -- a genuine
    simulation of what `python -m build --wheel` would embed, not a placeholder
    shape, so the orchestrator-affordance *.md content is proven to actually
    resolve rather than merely asserting a directory exists.
    """
    for lhs, rhs in force_include.items():
        source = REPO_ROOT / lhs
        if not source.exists():
            continue
        destination = fake_site_packages / rhs
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(source, destination)


@pytest.fixture()
def resolved_runtime_assets_root(patched_force_include_map, tmp_path) -> Path:
    """Drive the REAL des_plugin runtime-asset resolver against the simulated wheel.

    End-to-end simulation of a pipx install: materialise the force-include map
    as a fake site-packages tree, point `framework_source` at
    `fake_site_packages/nWave` (the value `install_nwave.py` assigns on a pipx
    install), then invoke `DESPlugin._install_nwave_runtime_assets` -- the REAL
    production method, never a re-implementation of its resolution logic -- and
    return the root where it lands the assets (`<claude_dir>/lib/nWave`).
    """
    fake_site_packages = tmp_path / "fake_site_packages"
    _materialize_wheel_tree(patched_force_include_map, fake_site_packages)

    framework_source = fake_site_packages / "nWave"
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)

    context = InstallContext(
        claude_dir=claude_dir,
        scripts_dir=tmp_path / "scripts",
        templates_dir=framework_source / "templates",
        logger=MagicMock(),
        project_root=None,
        framework_source=framework_source,
    )
    DESPlugin()._install_nwave_runtime_assets(context=context, using_prebuilt=True)

    return claude_dir / "lib" / "nWave"


# ---------------------------------------------------------------------------
# Scenario 1 -- every required runtime asset resolves through the simulated
# pipx layout (parametrized over the des_plugin's own constants -- max density).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("asset_dir_name", REQUIRED_ASSET_DIRS)
def test_wheel_resolves_required_runtime_asset_dir(
    resolved_runtime_assets_root, asset_dir_name
):
    """Each `_NWAVE_RUNTIME_ASSET_DIRS` entry lands under a pipx install.

    RED today for "flavors" and "data" (absent from the force-include map
    entirely) and for "templates" / "schemas" (mapped to a destination one
    level short of the "nWave/nWave/<name>" prefix the pipx resolution
    requires) -- so `resolved_runtime_assets_root` (<claude_dir>/lib/nWave/)
    never gets created and every one of these lookups fails.
    """
    resolved = resolved_runtime_assets_root / asset_dir_name
    assert resolved.is_dir(), (
        f"required runtime asset dir {asset_dir_name!r} does not resolve at "
        f"{resolved} -- the wheel force-include map does not ship it to the "
        "destination the des_plugin's runtime-asset resolver reads on a pipx "
        "install (framework_source / 'nWave' / <name>)"
    )


@pytest.mark.parametrize("asset_file_name", REQUIRED_ASSET_FILES)
def test_wheel_resolves_required_runtime_asset_file(
    resolved_runtime_assets_root, asset_file_name
):
    """Each `_NWAVE_RUNTIME_ASSET_FILES` entry lands under a pipx install.

    RED today: "nWave/framework-catalog.yaml" maps to a destination without
    the "nWave/nWave/..." prefix the pipx resolution requires.
    """
    resolved = resolved_runtime_assets_root / asset_file_name
    assert resolved.is_file(), (
        f"required runtime asset file {asset_file_name!r} does not resolve at "
        f"{resolved} -- the wheel force-include map does not ship it to the "
        "destination the des_plugin's runtime-asset resolver reads on a pipx "
        "install (framework_source / 'nWave' / <name>)"
    )


# ---------------------------------------------------------------------------
# Scenario 2 -- the affordance content specifically resolves (the content this
# bugfix exists to protect: the SessionStart orchestrator-affordance nudges).
# ---------------------------------------------------------------------------


def test_wheel_resolves_orchestrator_affordance_content(resolved_runtime_assets_root):
    """`nWave/data/orchestrator-affordance/*.md` resolves through a pipx install.

    This is the concrete victim named in the charter: without it, the
    SessionStart orchestrator-affordance injection is silently inert on every
    PyPI install. RED today because "data" is entirely absent from the
    force-include map, so `resolved_runtime_assets_root / "data"` never exists.
    """
    affordance_dir = resolved_runtime_assets_root / "data" / "orchestrator-affordance"
    assert affordance_dir.is_dir(), (
        f"nWave/data/orchestrator-affordance/ does not resolve at {affordance_dir} "
        "through the simulated pipx layout -- the affordance content this "
        "bugfix exists to protect is unresolvable on a PyPI install"
    )
    affordance_md_files = list(affordance_dir.glob("*.md"))
    assert len(affordance_md_files) >= 1, (
        f"nWave/data/orchestrator-affordance/ resolved at {affordance_dir} but "
        "carries zero *.md files -- the affordance content itself did not "
        "make it through the simulated pipx layout"
    )


# ---------------------------------------------------------------------------
# Scenario 3 -- negative-AT (required for the seal): asserts the WRONG state
# (an omitted required asset dir) is NOT produced by the current force-include
# map. Name carries "_not_" so `des verify-negative-at` can detect it.
# ---------------------------------------------------------------------------


def test_wheel_does_not_omit_runtime_asset_dirs(resolved_runtime_assets_root):
    """None of `_NWAVE_RUNTIME_ASSET_DIRS` is omitted by the wheel force-include map.

    The exact defect this bugfix closes: today the resolved set OMITS
    "flavors" and "data" entirely (absent from the map) and effectively omits
    "templates"/"schemas" too (destination one level short of the required
    prefix, so nothing resolves under a pipx layout). This must be the empty
    list once the fix lands.
    """
    missing_asset_dirs = [
        name
        for name in REQUIRED_ASSET_DIRS
        if not (resolved_runtime_assets_root / name).is_dir()
    ]
    assert missing_asset_dirs == [], (
        f"wheel force-include map omits runtime asset dir(s) {missing_asset_dirs} "
        f"-- these never resolve at {resolved_runtime_assets_root} through the "
        "simulated pipx layout, so a pipx install ships the des_plugin CODE "
        "but not this RUNTIME CONTENT"
    )


# ---------------------------------------------------------------------------
# Scenario 4 -- additive preservation: the pre-existing agents/skills
# force-include entries survive the fix (never removed by it).
# ---------------------------------------------------------------------------


def test_wheel_still_ships_agents_and_skills_after_patch(patched_force_include_map):
    """The existing `nWave/agents` + `nWave/skills` force-include entries persist.

    Guards against a fix that removes or narrows the pre-existing public-agent
    / skill selection while adding the missing runtime-asset entries -- the fix
    must be strictly additive.
    """
    assert patched_force_include_map.get("nWave/agents") == "nWave/agents", (
        "the 'nWave/agents' force-include entry is missing or changed -- the "
        "runtime-asset fix must be additive, not a replacement of the "
        "pre-existing public-agent selection"
    )
    assert patched_force_include_map.get("nWave/skills") == "nWave/skills", (
        "the 'nWave/skills' force-include entry is missing or changed -- the "
        "runtime-asset fix must be additive, not a replacement of the "
        "pre-existing skill selection"
    )
