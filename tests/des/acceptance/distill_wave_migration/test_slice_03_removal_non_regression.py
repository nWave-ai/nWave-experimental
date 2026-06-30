"""Slice-03 removal + non-regression AT runner.

Binds the slice-03 feature to its step definitions. The `*`-import registers
every `@given/@when/@then` for pytest-bdd collection.
"""

from __future__ import annotations

from distill_gate_steps.steps_slice_03 import *
from pytest_bdd import scenarios


scenarios("slice_03_removal_non_regression.feature")
