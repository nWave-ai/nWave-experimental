"""Slice-04 discrimination-boundary AT runner.

slice-01 is imported first so the reused dispatcher-run When registers in this
test module's namespace.
"""

from __future__ import annotations

from gate_steps.steps_slice_01 import *
from gate_steps.steps_slice_04 import *
from pytest_bdd import scenarios


scenarios("slice_04_discrimination_boundary.feature")
