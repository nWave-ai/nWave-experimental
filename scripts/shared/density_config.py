"""Thin re-export of the ONE documentation-density cascade.

The cascade itself lives in :mod:`des.domain.documentation_density`, because the
installed ``des`` runtime cannot import ``scripts`` (see that module's docstring
for the measured packaging-tier reason). This module stays as the import name
the non-``des`` callers already use — the ``nwave_ai`` CLI and the doctor density
check — so there is still exactly ONE resolver and ONE set of legal values.

Adding logic here would create a second cascade. Do not.
"""

from __future__ import annotations

from des.domain.documentation_density import (
    Density,
    DensityMode,
    ExpansionPromptMode,
    resolve_density,
)


__all__ = ["Density", "DensityMode", "ExpansionPromptMode", "resolve_density"]
