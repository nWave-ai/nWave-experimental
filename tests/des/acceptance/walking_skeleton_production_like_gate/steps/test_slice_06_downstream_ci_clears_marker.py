"""pytest-bdd binding for slice-06-downstream-ci-clears-marker.

Thin binding (Mandate-12 / Mandate 10 shared-vocabulary contract): this module
only registers the slice's scenarios and re-exports the shared step vocabulary
from `common_steps`. No step definitions or business logic live here -- the
DSL lives in `common_steps.py` over the typed domain concepts in
`domain_types.py`, and the SSOT logic lives in `composition.py`.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from .common_steps import *  # noqa: F403 -- shared step vocabulary


scenarios("../slice-06-downstream-ci-clears-marker.feature")
