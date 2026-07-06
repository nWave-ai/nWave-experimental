"""RobustnessDensityPort -- driven port: a per-language robustness-density facet (C4).

Feature `unified-language-adapter-registry`, slice-01 prefactoring (ADR-ULAR-001).
Structural (``typing.Protocol``), matching the EXISTING ``RunFacet``/``ListFacet``
Protocol shape in ``runner_registry.py`` (DDD-U3/technology-choices).

A concrete adapter (e.g. the slice-02 ``PythonRobustnessDensityAdapter``) WRAPS
the existing ``*.py`` glob + ``# domain:`` comment-scan body in
``check_robustness_density.py``'s ``_covered_domain_ids`` verbatim.

Registered into ``LanguageAdapterRegistry.register_robustness_density(name, facet)``
under the RESOLVED TOOL-NAME (``RunnerAdapter.name``), the SAME key
``GLOBAL_REGISTRY.lookup()`` already uses (DDD-U5) -- never ``target_language``.

Stdlib-only at import time (``__future__`` + ``typing``), per F-D-09 (no
``scripts.*`` import from ``src/des/**``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:
    from pathlib import Path


class RobustnessDensityPort(Protocol):
    """Driven port: a per-language robustness-density facet.

    ``covered_domain_ids`` returns the set of ``# domain: <id>``-tagged domain
    ids found in the staged AT scope, mirroring the existing
    ``_covered_domain_ids`` presence-check body.
    """

    def covered_domain_ids(self, at_scope_dir: Path) -> set[str]:
        """Return the domain ids tagged by a ``# domain: <id>`` marker."""
        ...


__all__ = ["RobustnessDensityPort"]
