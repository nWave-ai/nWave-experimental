"""GOLDEN FIXTURE (planted violation -- @given at layer 3+) -- M9 PBT-layer gate.

This file is NOT a real test. It is the recall-half corpus the slice-04 gate
scans: a ``@given``-decorated property-based test that, when CLASSIFIED AT A
LAYER-3+ FILE (the composition supplies a synthetic ``integration`` path), is a
Mandate-9 violation -- PBT machinery belongs at layers 1-2 only. The M9 rule
MUST flag it (``detect(...).flagged is True``), naming the offending construct
``test_install_plan_is_total_at_integration`` as a ``given_at_layer_3plus``
breach.

A gate that cannot flag this planted violation is itself testing-theater
(ADR-TEST-002 D-E). A property test against a real adapter pays the generative
cost (100ms-seconds per example) at the wrong layer -- exactly the slow-PBT
mislabel the mandate exists to catch.

The ``given`` / ``st`` symbols below are stand-in domain helpers so the corpus
parses; the gate reads structure (the ``@given`` decorator + the layer), not
behaviour.
"""

from hypothesis import given
from hypothesis import strategies as st


@given(st.integers(min_value=0, max_value=100))
def test_install_plan_is_total_at_integration(item_count):
    # VIOLATION (when read at layer 3+): a generative property test against what
    # the synthetic path declares is a real-adapter integration layer.
    assert item_count >= 0
