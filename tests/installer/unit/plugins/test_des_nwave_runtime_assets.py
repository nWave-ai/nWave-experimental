"""Regression: DES install ships nWave runtime assets to <claude_dir>/lib/nWave/.

F-DES-INSTALL-SHIPS-NWAVE-RUNTIME-ASSETS — the installed des package resolves
config siblings of lib/python at runtime (Path(__file__).parents[N] / "nWave" /
...): carpaccio_intercept reads nWave/flavors/atdd_pure.yaml, log_persistence
reads nWave/data/, the tdd/roadmap loaders read nWave/templates +
nWave/schemas, carpaccio_slice_gate reads nWave/framework-catalog.yaml. The
installer shipped only the code (lib/python/des) and never these assets, so
every atdd_pure dispatch crashed with a missing lib/nWave/flavors/atdd_pure.yaml.
These tests pin the shipping so the gap cannot silently reopen.
"""

from pathlib import Path
from unittest.mock import MagicMock

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.des_plugin import DESPlugin


def _context_with_nwave(base: Path) -> tuple[InstallContext, Path]:
    """Build an InstallContext whose project_root/nWave carries runtime assets."""
    project_root = base / "project"
    nwave = project_root / "nWave"
    (nwave / "flavors").mkdir(parents=True)
    (nwave / "flavors" / "atdd_pure.yaml").write_text("id: atdd_pure\n")
    (nwave / "templates").mkdir(parents=True)
    (nwave / "templates" / "step-tdd-cycle-schema.json").write_text("{}\n")
    (nwave / "framework-catalog.yaml").write_text("agents: []\n")

    claude_dir = base / ".claude"
    claude_dir.mkdir(parents=True)
    context = InstallContext(
        claude_dir=claude_dir,
        scripts_dir=base / "scripts",
        templates_dir=nwave / "templates",
        logger=MagicMock(),
        project_root=project_root,
        framework_source=None,
    )
    return context, claude_dir


def test_runtime_assets_shipped_to_lib_nwave(tmp_path: Path) -> None:
    """The flavor, data, template, schema dirs + catalog land under lib/nWave/.

    The carpaccio_intercept crash that broke every atdd_pure dispatch was the
    absence of lib/nWave/flavors/atdd_pure.yaml — this is the load-bearing slot.
    """
    context, claude_dir = _context_with_nwave(tmp_path)

    DESPlugin()._install_nwave_runtime_assets(context=context, using_prebuilt=False)

    lib_nwave = claude_dir / "lib" / "nWave"
    # The load-bearing slot: the flavor the carpaccio_intercept resolves.
    assert (lib_nwave / "flavors" / "atdd_pure.yaml").is_file()
    assert (lib_nwave / "templates" / "step-tdd-cycle-schema.json").is_file()
    assert (lib_nwave / "framework-catalog.yaml").is_file()
    assert not (lib_nwave / "hooks").exists()


def test_missing_nwave_source_skips_without_crash(tmp_path: Path) -> None:
    """A pre-built tree without a co-located nWave/ is a logged skip, not a crash.

    Named residue: the dist/PyPI path does not yet carry these assets beside its
    des package; the installer must degrade gracefully there, not raise.
    """
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)
    context = InstallContext(
        claude_dir=claude_dir,
        scripts_dir=tmp_path / "scripts",
        templates_dir=tmp_path / "templates",
        logger=MagicMock(),
        project_root=tmp_path / "absent-project",  # no nWave/ here
        framework_source=None,
    )

    # Must not raise.
    DESPlugin()._install_nwave_runtime_assets(context=context, using_prebuilt=False)

    assert not (claude_dir / "lib" / "nWave").exists()


def test_dry_run_ships_nothing(tmp_path: Path) -> None:
    """Dry-run reports intent without writing assets."""
    context, claude_dir = _context_with_nwave(tmp_path)
    context.dry_run = True

    DESPlugin()._install_nwave_runtime_assets(context=context, using_prebuilt=False)

    assert not (claude_dir / "lib" / "nWave").exists()


def test_nested_wheel_runtime_uses_flat_des_templates_when_required(
    tmp_path: Path,
) -> None:
    """A public wheel keeps DES prerequisites and runtime templates coherent.

    Hatch normalizes two force-include keys differing only by a trailing slash
    to one source path.  The wheel must therefore carry templates flat for the
    DES prerequisite, while the nested runtime tier falls back to that same
    canonical source when it populates ``lib/nWave/templates``.
    """
    framework_source = tmp_path / "site-packages" / "nWave"
    nested = framework_source / "nWave"
    (nested / "data").mkdir(parents=True)
    (nested / "data" / "doctor.json").write_text("{}\n")
    (nested / "framework-catalog.yaml").write_text("agents: []\n")
    (framework_source / "templates").mkdir(parents=True)
    (framework_source / "templates" / ".pre-commit-config-nwave.yaml").write_text(
        "repos: []\n"
    )

    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    context = InstallContext(
        claude_dir=claude_dir,
        scripts_dir=tmp_path / "scripts",
        templates_dir=framework_source / "templates",
        logger=MagicMock(),
        project_root=None,
        framework_source=framework_source,
    )

    DESPlugin()._install_nwave_runtime_assets(context=context, using_prebuilt=True)

    expected = (
        claude_dir / "lib" / "nWave" / "templates" / ".pre-commit-config-nwave.yaml"
    )
    assert expected.is_file(), (
        f"WHAT  {expected} was not created.\n"
        "WHY   Hatch normalizes the two force-include keys "
        "('nWave/templates' and 'nWave/templates/') to the SAME source "
        "path, so `_install_nwave_runtime_assets` must fall back to the "
        "flat `framework_source / 'templates'` tree when populating "
        "`lib/nWave/templates` for a nested wheel runtime -- that "
        "fallback did not fire (or fired against the wrong source).\n"
        "HOW   Inspect `DESPlugin._install_nwave_runtime_assets` "
        "(scripts/install/plugins/des_plugin.py) for the branch that "
        "populates `lib/nWave/templates` under `using_prebuilt=True`; "
        "confirm it reads from `context.templates_dir` "
        "(here: framework_source/templates), not from the nested "
        "`framework_source/nWave/...` tree that only carries `data` and "
        "`framework-catalog.yaml` in this fixture."
    )


def test_public_wheel_data_tier_installs_without_a_development_checkout(
    tmp_path: Path,
) -> None:
    """The packaged data tier serves an all-target install from its wheel alone."""
    framework_source = tmp_path / "site-packages" / "nWave"
    packaged_data = framework_source / "nWave" / "data"
    packaged_data.mkdir(parents=True)
    (packaged_data / "orchestrator-affordance.yaml").write_text("entries: []\n")
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    context = InstallContext(
        claude_dir=claude_dir,
        scripts_dir=tmp_path / "scripts",
        templates_dir=framework_source / "templates",
        logger=MagicMock(),
        project_root=None,
        framework_source=framework_source,
    )

    result = DESPlugin()._install_des_data(context)

    assert result.success is True, result.message
    assert (claude_dir / "data" / "orchestrator-affordance.yaml").is_file()
