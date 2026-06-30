"""PipTargetInstaller -- install a built artifact into a clean prefix.

Driven adapter for feature `walking-skeleton-production-like-gate` (DESIGN /
Staged-Install Fixture, step 3; Component Decomposition). Installs the built
artifact into a fresh, isolated prefix with `pip install --target` -- the D2
zero-new-dep floor (Python+pip only, no Docker).

The installed prefix is what the feature's `@walking-skeleton` AT runs
against (`PYTHONPATH={prefix}`) -- guaranteeing the AT exercises the
*installed* artifact, never the developer's `src/` tree.

Real I/O: a real `pip install --target` subprocess against a real prefix.
"""

from __future__ import annotations

from pathlib import Path

from des.ports.driven_ports.staged_installer import (
    InstalledTree,
    StagedInstaller,
    StagedInstallError,
)
from des.runtime.interpreter import des_spawn


class PipTargetInstaller(StagedInstaller):
    """Install a built artifact into a clean prefix via `pip install --target`."""

    def install(self, artifact: Path, prefix: Path) -> InstalledTree:
        """Install `artifact` into `prefix`; return the staged `InstalledTree`.

        Raises `StagedInstallError` when the artifact is missing or the
        install subprocess fails.
        """
        artifact = Path(artifact)
        prefix = Path(prefix)
        if not artifact.is_file():
            raise StagedInstallError(f"artifact does not exist: {artifact}")
        prefix.mkdir(parents=True, exist_ok=True)
        result = des_spawn(
            None,
            "pip",
            "install",
            "--no-deps",
            "--no-index",
            "--target",
            str(prefix),
            str(artifact),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise StagedInstallError(
                f"pip install --target failed (exit {result.returncode}): "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        return InstalledTree(prefix=prefix, python_path=prefix)


__all__ = ["PipTargetInstaller"]
