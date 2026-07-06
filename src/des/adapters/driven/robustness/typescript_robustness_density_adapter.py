"""TypeScriptRobustnessDensityAdapter -- TS RobustnessDensityPort facet (C13).

unified-language-adapter-registry slice-03 (DESIGN slice-07, component C13).
Registered by ``nwave_lang_typescript`` under the resolved tool-name
``"vitest"`` so ``registry.lookup_robustness_density("vitest")`` resolves
(the slice-03 unification pin, scenario 2). Mirrors
``PythonRobustnessDensityAdapter`` (C10) EXACTLY: wiring the ``# domain:``
marker-scan routing through the gate CLI is a documented future slice -- not
required by any slice-03 AT, so this facet's method body is not exercised
here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


class TypeScriptRobustnessDensityAdapter:
    """The TypeScript robustness-density facet (routing: future slice)."""

    def covered_domain_ids(self, at_scope_dir: Path) -> set[str]:
        raise NotImplementedError(
            "TypeScriptRobustnessDensityAdapter.covered_domain_ids is a "
            "documented future slice -- no slice-03 AT exercises it"
        )


__all__ = ["TypeScriptRobustnessDensityAdapter"]
