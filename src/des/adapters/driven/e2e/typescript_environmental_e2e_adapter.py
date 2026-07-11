"""TypeScriptEnvironmentalE2EAdapter -- TS EnvironmentalE2EPort facet (C13).

unified-language-adapter-registry slice-03 (DESIGN slice-07, component C13).
Registered by ``nwave_lang_typescript`` under the resolved tool-name
``"vitest"`` so ``registry.lookup_environmental_e2e("vitest")`` resolves (the
slice-03 unification pin, scenario 2). Mirrors
``PythonEnvironmentalE2EAdapter`` (C9) EXACTLY.

``implement-language-adapter-facets`` slice-04 (D9): ``build``/``install``
are pure composition (has-a, DDD-03) over 2 NEW ``ArtifactBuilder``/
``StagedInstaller`` implementations, ``NpmPackArtifactBuilder`` (D6) /
``NpmInstallStagedInstaller`` (D7) -- each method constructs its own
delegate and returns its return value unchanged, letting
``ArtifactBuildError``/``StagedInstallError`` propagate verbatim.
``run_against_installed`` delegates to the shared
``vitest_e2e_runner.run_vitest_against_installed`` helper (D8), the TS
mirror of D3's Python ``pytest_e2e_runner``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from des.adapters.driven.build.npm_pack_artifact_builder import (
    NpmPackArtifactBuilder,
)
from des.adapters.driven.e2e.vitest_e2e_runner import run_vitest_against_installed
from des.adapters.driven.install.npm_install_staged_installer import (
    NpmInstallStagedInstaller,
)


if TYPE_CHECKING:
    from pathlib import Path

    from des.ports.driven_ports.staged_installer import InstalledTree


class TypeScriptEnvironmentalE2EAdapter:
    """The TypeScript environmental-e2e facet."""

    def build(self, feature_root: Path) -> Path:
        """Delegate to a composed `NpmPackArtifactBuilder`; return its artifact."""
        return NpmPackArtifactBuilder().build(feature_root)

    def install(self, artifact: Path, prefix: Path) -> InstalledTree:
        """Delegate to a composed `NpmInstallStagedInstaller`; return its `InstalledTree`."""
        return NpmInstallStagedInstaller().install(artifact, prefix)

    def run_against_installed(
        self,
        e2e_path: Path,
        prefix: Path,
        junit_path: Path,
        work_dir: Path,
    ) -> None:
        """Run vitest against the staged prefix; write JUnit XML at `junit_path`."""
        run_vitest_against_installed(e2e_path, prefix, junit_path, work_dir)


__all__ = ["TypeScriptEnvironmentalE2EAdapter"]
