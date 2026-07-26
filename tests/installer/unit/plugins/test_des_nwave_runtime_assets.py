"""Regression: DES install ships nWave runtime assets to <claude_dir>/lib/nWave/.

F-DES-INSTALL-SHIPS-NWAVE-RUNTIME-ASSETS — the installed des package resolves
config siblings of lib/python at runtime (Path(__file__).parents[N] / "nWave" /
...): carpaccio_intercept reads nWave/flavors/atdd_pure.yaml, log_persistence +
doctor read nWave/data/, the tdd/roadmap loaders read nWave/templates +
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
    (nwave / "data").mkdir(parents=True)
    (nwave / "data" / "language-adapter-ports.yaml").write_text("ports: []\n")
    (nwave / "templates").mkdir(parents=True)
    (nwave / "templates" / "step-tdd-cycle-schema.json").write_text("{}\n")
    (nwave / "schemas").mkdir(parents=True)
    (nwave / "schemas" / "atdd-pure-phase-sequence.schema.json").write_text("{}\n")
    (nwave / "framework-catalog.yaml").write_text("agents: []\n")
    hooks = project_root / "scripts" / "hooks"
    hooks.mkdir(parents=True)
    (hooks / "orchestrator_affordance_refresh.py").write_text("print('hook')\n")

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
    assert (lib_nwave / "data" / "language-adapter-ports.yaml").is_file()
    assert (lib_nwave / "templates" / "step-tdd-cycle-schema.json").is_file()
    assert (lib_nwave / "schemas" / "atdd-pure-phase-sequence.schema.json").is_file()
    assert (lib_nwave / "framework-catalog.yaml").is_file()
    assert (lib_nwave / "hooks" / "orchestrator_affordance_refresh.py").is_file()


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
