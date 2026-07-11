"""PythonEnvironmentalE2EAdapter -- the Python reference EnvironmentalE2EPort facet (C9).

unified-language-adapter-registry slice-02 (DESIGN slice-05a, component C9).
Registered by ``nwave_lang_python`` under the resolved tool-name ``"pytest"``
so ``registry.lookup_environmental_e2e("pytest")`` resolves (the slice-02
unification pin, scenario 3).

``implement-language-adapter-facets`` slice-03 (D3/D4/D5): ``build``/
``install`` are pure composition (has-a, DDD-01) over the existing
``BuildDistArtifactBuilder``/``PipTargetInstaller`` adapters -- each method
constructs its own delegate and returns its return value unchanged, letting
``ArtifactBuildError``/``StagedInstallError`` propagate verbatim.
``run_against_installed`` delegates to the shared
``pytest_e2e_runner.run_pytest_against_installed`` helper (DDD-02), the same
implementation ``des.cli.verify_environmental_e2e``'s own fallback path uses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from des.adapters.driven.build.build_dist_artifact_builder import (
    BuildDistArtifactBuilder,
)
from des.adapters.driven.e2e.pytest_e2e_runner import run_pytest_against_installed
from des.adapters.driven.install.pip_target_installer import PipTargetInstaller


if TYPE_CHECKING:
    from pathlib import Path

    from des.ports.driven_ports.staged_installer import InstalledTree


class PythonEnvironmentalE2EAdapter:
    """The Python reference environmental-e2e facet."""

    def build(self, feature_root: Path) -> Path:
        """Delegate to a composed `BuildDistArtifactBuilder`; return its artifact."""
        return BuildDistArtifactBuilder().build(feature_root)

    def install(self, artifact: Path, prefix: Path) -> InstalledTree:
        """Delegate to a composed `PipTargetInstaller`; return its `InstalledTree`."""
        return PipTargetInstaller().install(artifact, prefix)

    def run_against_installed(
        self,
        e2e_path: Path,
        prefix: Path,
        junit_path: Path,
        work_dir: Path,
    ) -> None:
        """Run pytest against the staged prefix; write JUnit XML at `junit_path`."""
        run_pytest_against_installed(e2e_path, prefix, junit_path, work_dir)


__all__ = ["PythonEnvironmentalE2EAdapter"]
