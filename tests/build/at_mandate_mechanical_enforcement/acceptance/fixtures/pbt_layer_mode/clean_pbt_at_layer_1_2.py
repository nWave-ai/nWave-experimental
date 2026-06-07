"""GOLDEN FIXTURE (clean -- PBT at layer 1-2) -- M9 PBT-layer-mode gate.

This file is NOT a real test. It is the precision-half corpus the slice-04 gate
scans: a ``@given`` property test AND a ``RuleBasedStateMachine`` model that,
when CLASSIFIED AT A LAYER-1-2 FILE (the composition supplies a synthetic
``unit`` path), are COMPLIANT -- layers 1-2 (unit, in-memory acceptance) are
PBT's home (Mandate 9). The M9 rule MUST NOT flag it
(``detect(...).flagged is False``).

The gate must approach 100% precision: a false-positive here -- flagging
legitimate PBT at its correct layer -- would block a commit. This is the exact
construct the violation fixtures carry, distinguished ONLY by layer, proving the
gate keys on (construct AND layer), never construct alone.

The ``given`` / ``st`` / ``RuleBasedStateMachine`` symbols are stand-in helpers
so the corpus parses; the gate reads structure + layer, not behaviour.
"""

from hypothesis import given
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule


@given(st.integers(min_value=0, max_value=100))
def test_total_is_non_negative_at_unit(item_count):
    # COMPLIANT at layer 1-2: a generative property test at PBT's home layer.
    assert item_count >= 0


class TotalsJourney(RuleBasedStateMachine):
    # COMPLIANT at layer 1-2: stateful PBT at its home layer (Tier B is in-memory).
    @rule()
    def add(self):
        pass
