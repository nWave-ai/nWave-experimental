"""TypeScriptEnvironmentalE2EAdapter -- TS EnvironmentalE2EPort facet (C13).

unified-language-adapter-registry slice-03 (DESIGN slice-07, component C13).
Registered by ``nwave_lang_typescript`` under the resolved tool-name
``"vitest"`` so ``registry.lookup_environmental_e2e("vitest")`` resolves (the
slice-03 unification pin, scenario 2). Mirrors
``PythonEnvironmentalE2EAdapter`` (C9) EXACTLY: DDD-U4 delegates
``build``/``install`` to the existing ``ArtifactBuilder``/``StagedInstaller``
ports; wiring that delegation end-to-end through the gate CLI is a documented
future slice (feature-delta ``[REF] Open questions``) -- not required by any
slice-03 AT, so this facet's method bodies are not exercised here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path

    from des.ports.driven_ports.staged_installer import InstalledTree


class TypeScriptEnvironmentalE2EAdapter:
    """The TypeScript environmental-e2e facet (routing: future slice)."""

    def build(self, feature_root: Path) -> Path:
        raise NotImplementedError(
            "TypeScriptEnvironmentalE2EAdapter.build is a documented future "
            "slice (feature-delta [REF] Open questions) -- no slice-03 AT "
            "exercises it"
        )

    def install(self, artifact: Path, prefix: Path) -> InstalledTree:
        raise NotImplementedError(
            "TypeScriptEnvironmentalE2EAdapter.install is a documented "
            "future slice (feature-delta [REF] Open questions) -- no "
            "slice-03 AT exercises it"
        )

    def run_against_installed(
        self,
        e2e_path: Path,
        prefix: Path,
        junit_path: Path,
        work_dir: Path,
    ) -> None:
        raise NotImplementedError(
            "TypeScriptEnvironmentalE2EAdapter.run_against_installed is a "
            "documented future slice (feature-delta [REF] Open questions) "
            "-- no slice-03 AT exercises it"
        )


__all__ = ["TypeScriptEnvironmentalE2EAdapter"]
