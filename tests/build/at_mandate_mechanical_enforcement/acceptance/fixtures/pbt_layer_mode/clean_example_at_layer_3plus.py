"""GOLDEN FIXTURE (clean near-miss -- example test at layer 3+) -- M9 gate.

This file is NOT a real test. It is the precision-half near-miss corpus the
slice-04 gate scans: an EXAMPLE-BASED test that, when CLASSIFIED AT A LAYER-3+
FILE (the composition supplies a synthetic ``integration`` path), is COMPLIANT --
example-based tests are exactly what belongs at layers 3+ (Mandate 9, Mandate
11: sad paths enumerated, never PBT-generated). It carries the near-miss trap a
naive scanner would over-fire on: a ``from hypothesis import strategies``
mention in a COMMENT and a function literally named with ``given`` in its text,
neither of which is an actual ``@given`` decorator or stateful import. The M9
rule MUST NOT flag it (``detect(...).flagged is False``).

The gate must approach 100% precision: flagging a legitimate example-based test
at layer 3+ would block a commit and push authors back toward the slow-PBT
anti-pattern the mandate forbids. The trap proves the gate keys on the STRUCTURAL
PBT construct (an applied ``@given`` decorator / a stateful import), never a
textual mention of ``given`` or ``hypothesis``.

The ``assert_install_plan`` symbol is a stand-in helper so the corpus parses;
the gate reads structure + layer, not behaviour.
"""


def assert_install_plan(item_count):
    return item_count >= 0


# Near-miss trap: a textual "from hypothesis import given" mention in a comment,
# and a test named with "given" -- neither is a structural PBT construct.
def test_install_plan_for_a_given_count_at_integration():
    # COMPLIANT at layer 3+: an enumerated example test (no @given, no stateful
    # import) -- exactly what belongs at the integration layer.
    assert assert_install_plan(3)
