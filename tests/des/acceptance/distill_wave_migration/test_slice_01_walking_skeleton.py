"""Slice-01 walking-skeleton AT runner.

Binds the slice-01 feature to its step definitions. The `*`-import registers
every `@given/@when/@then` for pytest-bdd collection.
"""

from __future__ import annotations

from distill_gate_steps.steps_slice_01 import *
from pytest_bdd import scenarios


scenarios("slice_01_walking_skeleton.feature")
