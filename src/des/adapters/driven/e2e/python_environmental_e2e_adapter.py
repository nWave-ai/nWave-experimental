"""PythonEnvironmentalE2EAdapter -- the Python reference EnvironmentalE2EPort facet (C9).

unified-language-adapter-registry slice-02 (DESIGN slice-05a, component C9).
Registered by ``nwave_lang_python`` under the resolved tool-name ``"pytest"``
so ``registry.lookup_environmental_e2e("pytest")`` resolves (the slice-02
unification pin, scenario 3). DDD-U4 delegates ``build``/``install`` to the
existing ``ArtifactBuilder``/``StagedInstaller`` ports; wiring that delegation
end-to-end through the gate CLI is a documented future slice (feature-delta
``[REF] Open questions``) -- not required by any slice-02 AT, so this facet's
method bodies are not exercised here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path

    from des.ports.driven_ports.staged_installer import InstalledTree


class PythonEnvironmentalE2EAdapter:
    """The Python reference environmental-e2e facet (routing: future slice)."""

    def build(self, feature_root: Path) -> Path:
        raise NotImplementedError(
            "PythonEnvironmentalE2EAdapter.build is a documented future slice "
            "(feature-delta [REF] Open questions) -- no slice-02 AT exercises it"
        )

    def install(self, artifact: Path, prefix: Path) -> InstalledTree:
        raise NotImplementedError(
            "PythonEnvironmentalE2EAdapter.install is a documented future slice "
            "(feature-delta [REF] Open questions) -- no slice-02 AT exercises it"
        )

    def run_against_installed(
        self,
        e2e_path: Path,
        prefix: Path,
        junit_path: Path,
        work_dir: Path,
    ) -> None:
        raise NotImplementedError(
            "PythonEnvironmentalE2EAdapter.run_against_installed is a "
            "documented future slice (feature-delta [REF] Open questions) -- "
            "no slice-02 AT exercises it"
        )


__all__ = ["PythonEnvironmentalE2EAdapter"]
