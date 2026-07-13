"""NpmInstallStagedInstaller -- install a built npm tarball into a clean prefix.

Feature `implement-language-adapter-facets`, slice-04 (feature-delta.md
Component Decomposition D7). The TS mirror of `PipTargetInstaller` (D5's
Python sibling, `pip_target_installer.py`). Implements the EXISTING
`StagedInstaller` port (DDD-03) -- no port-body change; a 2nd concrete
implementation alongside the pip-based one.

Real I/O: a real `npm install --no-audit --no-fund --offline --prefix
<dir> <tarball>` subprocess. `npm` is resolved via the SHARED
`resolve_tool` discovery scale (reused from `VITEST_KNOWN_LOCATIONS`).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from des.adapters.driven.runner.tool_discovery import resolve_tool
from des.adapters.driven.runner.vitest_runner import VITEST_KNOWN_LOCATIONS
from des.ports.driven_ports.staged_installer import (
    InstalledTree,
    StagedInstaller,
    StagedInstallError,
)


class NpmInstallStagedInstaller(StagedInstaller):
    """Install a built npm tarball into a clean prefix (D7)."""

    def install(self, artifact: Path, prefix: Path) -> InstalledTree:
        """Install `artifact` into `prefix`; return the staged `InstalledTree`.

        Raises `StagedInstallError` when the artifact is missing, `npm`
        cannot be resolved, or the install subprocess fails.
        """
        artifact = Path(artifact)
        prefix = Path(prefix)
        if not artifact.is_file():
            raise StagedInstallError(f"artifact does not exist: {artifact}")
        resolution = resolve_tool("npm", VITEST_KNOWN_LOCATIONS, base_dir=prefix)
        if resolution.path is None:
            raise StagedInstallError(f"npm not found: {resolution.remediation}")
        prefix.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [
                resolution.path,
                "install",
                "--no-audit",
                "--no-fund",
                "--offline",
                "--prefix",
                str(prefix),
                str(artifact),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise StagedInstallError(
                f"npm install --prefix failed (exit {result.returncode}): "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        return InstalledTree(prefix=prefix, python_path=prefix)


__all__ = ["NpmInstallStagedInstaller"]
