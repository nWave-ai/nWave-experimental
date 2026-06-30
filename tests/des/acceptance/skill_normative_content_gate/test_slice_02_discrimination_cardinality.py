"""Slice-02 discrimination + cardinality AT runner.

The slice-01 steps module is imported first so the reused dispatcher-run When
and PASS-verdict Then are registered for pytest-bdd in this test module's
namespace (a `*`-import does not re-export names a module merely imported).
"""

from __future__ import annotations

from gate_steps.steps_slice_01 import *
from gate_steps.steps_slice_02 import *
from pytest_bdd import scenarios


scenarios("slice_02_discrimination_cardinality.feature")
