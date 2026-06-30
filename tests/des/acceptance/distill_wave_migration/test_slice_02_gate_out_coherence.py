"""Slice-02 gate-OUT coherence AT runner.

Binds the slice-02 feature to its step definitions. The `*`-import registers
every `@given/@when/@then` for pytest-bdd collection.
"""

from __future__ import annotations

from distill_gate_steps.steps_slice_02 import *
from pytest_bdd import scenarios


scenarios("slice_02_gate_out_coherence.feature")
