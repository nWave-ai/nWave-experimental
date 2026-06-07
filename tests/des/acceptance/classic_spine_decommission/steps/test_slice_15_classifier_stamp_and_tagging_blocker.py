"""Step bindings: slice-15 of classic-spine-decommission.

The feature-end-review gap slice. All steps resolve from the shared
`common_steps` vocabulary (Mandate 10 shared-vocabulary contract / Mandate-12
SSOT). This file only binds the `.feature` scenarios. RED scaffold until
DELIVER (conftest xfail hook lists `slice-15` in `_RED_SCAFFOLD_SLICES`).
"""

from __future__ import annotations

from pytest_bdd import scenarios

from .common_steps import *


scenarios("../slice-15-classifier-stamp-and-tagging-blocker.feature")
