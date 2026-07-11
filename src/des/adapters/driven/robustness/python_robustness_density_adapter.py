"""PythonRobustnessDensityAdapter -- Python reference RobustnessDensityPort facet (C10).

unified-language-adapter-registry slice-02 (DESIGN slice-05a, component C10).
Registered by ``nwave_lang_python`` under the resolved tool-name ``"pytest"``
so ``registry.lookup_robustness_density("pytest")`` resolves (the slice-02
unification pin, scenario 3).

implement-language-adapter-facets slice-01 (component D1): ``covered_domain_ids``
duplicates -- never imports (F-D-09: ``src/des/**`` cannot import ``scripts.*``)
-- the ``*.py`` glob + ``# domain:`` comment-scan body of
``check_robustness_density.py::_covered_domain_ids`` verbatim. Wiring this facet's
routing through the gate CLI remains a documented future slice.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


class PythonRobustnessDensityAdapter:
    """The Python reference robustness-density facet."""

    def covered_domain_ids(self, at_scope_dir: Path) -> set[str]:
        """Return the domain ids tagged by a ``# domain: <id>`` marker.

        Duplicated verbatim from
        ``scripts/cli/check_robustness_density.py::_covered_domain_ids``
        (D1 DDD-04) -- recursive ``*.py`` glob, exact ``"# domain:"``
        stripped-prefix match, empty markers contribute nothing, dedupe
        via ``set``.
        """
        covered: set[str] = set()
        for path in at_scope_dir.rglob("*.py"):
            for raw_line in path.read_text(encoding="utf-8").splitlines():
                stripped = raw_line.strip()
                if not stripped.startswith("# domain:"):
                    continue
                marker = stripped[len("# domain:") :].strip()
                if marker:
                    covered.add(marker)
        return covered


__all__ = ["PythonRobustnessDensityAdapter"]
