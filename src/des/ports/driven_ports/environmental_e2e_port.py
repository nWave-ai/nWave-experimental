"""EnvironmentalE2EPort -- driven port: a per-language environmental-e2e facet (C3).

Feature `unified-language-adapter-registry`, slice-01 prefactoring (ADR-ULAR-001).
Structural (``typing.Protocol``), matching the EXISTING ``RunFacet``/``ListFacet``
Protocol shape in ``runner_registry.py`` (DDD-U3/technology-choices).

DDD-U4: a concrete Python adapter (slice-02) delegates ``build``/``install`` to
the EXISTING, already-proven ``ArtifactBuilder``/``StagedInstaller`` ports rather
than re-implementing wheel-build/install -- only ``run_against_installed`` (the
pytest-against-installed leg, wrapping ``_run_e2e_against_installed`` verbatim)
is new adapter surface.

Registered into ``LanguageAdapterRegistry.register_environmental_e2e(name, facet)``
under the RESOLVED TOOL-NAME (``RunnerAdapter.name``), the SAME key
``GLOBAL_REGISTRY.lookup()`` already uses (DDD-U5) -- never ``target_language``.

Stdlib-only at import time (``__future__`` + ``typing`` + ``pathlib``), per F-D-09
(no ``scripts.*`` import from ``src/des/**``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:
    from pathlib import Path

    from des.ports.driven_ports.staged_installer import InstalledTree


class EnvironmentalE2EPort(Protocol):
    """Driven port: a per-language environmental-e2e facet.

    ``build``/``install`` delegate to ``ArtifactBuilder``/``StagedInstaller``
    (DDD-U4); ``run_against_installed`` runs the e2e test against the staged
    install and reports nothing observable of its own (the caller reads the
    written junit/results artifacts, mirroring ``_run_e2e_against_installed``).
    """

    def build(self, feature_root: Path) -> Path:
        """Build the delivered artifact; return the path to it."""
        ...

    def install(self, artifact: Path, prefix: Path) -> InstalledTree:
        """Install ``artifact`` into ``prefix``; return the ``InstalledTree``."""
        ...

    def run_against_installed(
        self,
        e2e_path: Path,
        prefix: Path,
        junit_path: Path,
        work_dir: Path,
    ) -> None:
        """Run the e2e test against the staged install; write ``junit_path``."""
        ...


__all__ = ["EnvironmentalE2EPort"]
