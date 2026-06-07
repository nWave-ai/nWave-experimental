"""GOLDEN FIXTURE (clean -- PBT sad path at its home layer 1-2) -- M11 gate.

This file is NOT a real test. It is the second precision-half corpus the slice-07
gate scans: a ``@given``-decorated sad-path property test that, when CLASSIFIED
AT A LAYER-1-2 FILE (the composition supplies a synthetic ``unit`` path), is
COMPLIANT -- PBT machinery is the default AT ITS HOME LAYER, where each example
is ~1-10ms (Mandate 9 / Mandate 11: the forbidden zone is layers 3+ only). The
M11 rule MUST NOT flag it (``detect(...).flagged is False``).

A gate that flags this is over-firing -- it would forbid PBT everywhere instead
of only at layers 3+ where the generative cost is incompatible with real I/O.

The ``given`` / ``st`` symbols below are stand-in domain helpers so the corpus
parses; the gate reads structure (the ``@given`` decorator + the layer).
"""

from hypothesis import given
from hypothesis import strategies as st


@given(st.integers(min_value=0, max_value=4096))
def test_install_fails_when_disk_full(free_bytes):
    # COMPLIANT (when read at layer 1-2): a generative sad-path property test at
    # PBT's home layer, where exploring the failure equivalence-class is cheap.
    assert free_bytes >= 0
