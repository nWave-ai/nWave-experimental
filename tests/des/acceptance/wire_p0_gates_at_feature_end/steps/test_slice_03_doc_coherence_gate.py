"""pytest-bdd binding for slice-03-doc-coherence-gate.

Thin binding (Mandate-12 / Mandate 10 shared-vocabulary contract): registers
the slice's scenario and re-exports the shared step vocabulary. No business
logic here.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from .common_steps import *


scenarios("../slice-03-doc-coherence-gate.feature")
