"""PythonRobustnessDensityAdapter -- Python reference RobustnessDensityPort facet (C10).

unified-language-adapter-registry slice-02 (DESIGN slice-05a, component C10).
Registered by ``nwave_lang_python`` under the resolved tool-name ``"pytest"``
so ``registry.lookup_robustness_density("pytest")`` resolves (the slice-02
unification pin, scenario 3). Wiring the ``# domain:`` marker-scan routing
through the gate CLI is a documented future slice -- not required by any
slice-02 AT, so this facet's method body is not exercised here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


class PythonRobustnessDensityAdapter:
    """The Python reference robustness-density facet (routing: future slice)."""

    def covered_domain_ids(self, at_scope_dir: Path) -> set[str]:
        raise NotImplementedError(
            "PythonRobustnessDensityAdapter.covered_domain_ids is a documented "
            "future slice -- no slice-02 AT exercises it"
        )


__all__ = ["PythonRobustnessDensityAdapter"]
