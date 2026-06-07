"""Step bindings: slice-06 of classic-spine-decommission.

All steps resolve from the shared `common_steps` vocabulary (Mandate 10
shared-vocabulary contract / Mandate-12 SSOT). This file only binds the
`.feature` scenarios. RED scaffold until DELIVER (conftest xfail hook).
"""

from __future__ import annotations

from pytest_bdd import scenarios

from .common_steps import *


scenarios("../slice-06-convert-sha-reverification.feature")
