"""pytest-bdd binding for slice-01-common-audit-log-writer.

Thin binding (Mandate-12 / Mandate 10 shared-vocabulary contract): registers
the slice's scenarios and re-exports the shared step vocabulary. No business
logic here.

AT-5 (correlation_id determinism PBT) is a separate Hypothesis-driven test
in the sibling ``test_slice_01_correlation_id_property.py`` module -- layer 1
PBT belongs OUTSIDE pytest-bdd's scenario binding (the .feature scenario
documents the invariant in domain language; the PBT is the executable
proof).
"""

from __future__ import annotations

from pytest_bdd import scenarios

from .common_steps import *  # noqa: F403 -- shared step vocabulary


scenarios("../slice-01-common-audit-log-writer.feature")
