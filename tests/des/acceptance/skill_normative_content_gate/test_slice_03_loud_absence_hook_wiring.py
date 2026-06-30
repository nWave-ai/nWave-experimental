"""Slice-03 loud-absence + hook-wiring AT runner.

slice-01 (dispatcher-run When) and slice-02 (INDETERMINATE-verdict Then) are
imported first so the reused steps register in this test module's namespace.
"""

from __future__ import annotations

from gate_steps.steps_slice_01 import *
from gate_steps.steps_slice_02 import *
from gate_steps.steps_slice_03 import *
from pytest_bdd import scenarios


scenarios("slice_03_loud_absence_hook_wiring.feature")
