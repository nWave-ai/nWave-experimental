"""pytest-bdd binding for slice-01 (walking-skeleton + bugfix regression).

Thin binding (Mandate-12 / Mandate 10 shared-vocabulary contract): this
module only registers the slice's scenarios and re-exports the shared step
vocabulary from ``common_steps``. No step definitions or business logic
live here.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from .common_steps import *


scenarios("../walking-skeleton.feature")
