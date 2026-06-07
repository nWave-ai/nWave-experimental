"""GOLDEN FIXTURE (planted violation -- PBT sad path at layer 3+) -- M11 gate.

This file is NOT a real test. It is the recall-half corpus the slice-07 gate
scans: a ``@given``-decorated sad-path property test that, when CLASSIFIED AT A
LAYER-3+ FILE (the composition supplies a synthetic ``integration`` path), is a
Mandate-11 violation -- at layers 3+ each generated example is real-I/O-heavy
(100ms-seconds), so sad paths MUST be enumerated example-by-example, never
PBT-generated. The M11 rule MUST flag it (``detect(...).flagged is True``),
naming the offending construct ``test_install_fails_when_disk_full`` as a
``pbt_in_layer3_sad_path`` breach.

A gate that cannot flag this planted violation is itself testing-theater
(ADR-TEST-002 D-E). This is the slow-PBT-sad-path mislabel the mandate exists to
catch -- the recast of the dormant ``check_robustness_density.py`` layer logic.

The ``given`` / ``st`` symbols below are stand-in domain helpers so the corpus
parses; the gate reads structure (the ``@given`` decorator + the layer), not
behaviour.
"""

from hypothesis import given
from hypothesis import strategies as st


@given(st.integers(min_value=0, max_value=4096))
def test_install_fails_when_disk_full(free_bytes):
    # VIOLATION (when read at layer 3+): a generative property test exploring a
    # sad path against what the synthetic path declares is a real-adapter
    # integration layer -- a sad path that should be ONE enumerated example.
    assert free_bytes >= 0
