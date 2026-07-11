"""TypeScriptRobustnessDensityAdapter -- TS RobustnessDensityPort facet (C13).

unified-language-adapter-registry slice-03 (DESIGN slice-07, component C13).
Registered by ``nwave_lang_typescript`` under the resolved tool-name
``"vitest"`` so ``registry.lookup_robustness_density("vitest")`` resolves
(the slice-03 unification pin, scenario 2).

implement-language-adapter-facets slice-02 (component D2): ``covered_domain_ids``
mirrors ``PythonRobustnessDensityAdapter.covered_domain_ids`` (C10) EXACTLY
(DDD-05) -- recursive ``*.ts``/``*.tsx`` glob (union, via
``itertools.chain``), the IDENTICAL language-agnostic ``"# domain:"``
stripped-prefix marker (not a TS-native ``// domain:`` comment), empty
markers contribute nothing, dedupe via ``set``. Wiring this facet's routing
through the gate CLI remains a documented future slice.
"""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


class TypeScriptRobustnessDensityAdapter:
    """The TypeScript robustness-density facet."""

    def covered_domain_ids(self, at_scope_dir: Path) -> set[str]:
        """Return the domain ids tagged by a ``# domain: <id>`` marker.

        Mirrors ``PythonRobustnessDensityAdapter.covered_domain_ids``
        exactly (D2 DDD-05) -- recursive ``*.ts``/``*.tsx`` glob union,
        exact ``"# domain:"`` stripped-prefix match, empty markers
        contribute nothing, dedupe via ``set``.
        """
        covered: set[str] = set()
        for path in itertools.chain(
            at_scope_dir.rglob("*.ts"), at_scope_dir.rglob("*.tsx")
        ):
            for raw_line in path.read_text(encoding="utf-8").splitlines():
                stripped = raw_line.strip()
                if not stripped.startswith("# domain:"):
                    continue
                marker = stripped[len("# domain:") :].strip()
                if marker:
                    covered.add(marker)
        return covered


__all__ = ["TypeScriptRobustnessDensityAdapter"]
