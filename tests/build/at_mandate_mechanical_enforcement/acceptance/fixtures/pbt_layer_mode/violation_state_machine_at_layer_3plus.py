"""GOLDEN FIXTURE (planted violation -- state machine at layer 3+) -- M9 gate.

This file is NOT a real test. It is the recall-half corpus the slice-04 gate
scans: a file importing a ``RuleBasedStateMachine`` (the stateful-PBT API) that,
when CLASSIFIED AT A LAYER-3+ FILE (the composition supplies a synthetic ``e2e``
path), is a Mandate-9 violation -- stateful PBT exploration belongs at the
in-memory Tier B (Mandate 10), never against a real adapter at layer 3+. The M9
rule MUST flag it (``detect(...).flagged is True``), naming the offending
construct ``RuleBasedStateMachine`` as a ``state_machine_at_layer_3plus`` breach.

A gate that cannot flag this planted violation is itself testing-theater
(ADR-TEST-002 D-E). A state-machine model driven against a real stack at layer
3+ multiplies real-I/O cost per generated command sequence -- the exact slow-PBT
mislabel the mandate forbids.

The ``RuleBasedStateMachine`` / ``rule`` symbols are imported only so the corpus
parses; the gate reads structure (the stateful-PBT import + the layer), not
behaviour.
"""

from hypothesis.stateful import RuleBasedStateMachine, rule


class InstallJourney(RuleBasedStateMachine):
    # VIOLATION (when read at layer 3+): a stateful-PBT model where, at the layer
    # the synthetic path declares, only example-based tests belong.
    @rule()
    def install(self):
        pass
