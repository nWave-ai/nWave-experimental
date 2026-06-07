# Meta-gate planted fixture (incomplete_gate, RECALL TARGET).
#
# `orphan_gate` is a DELIBERATELY-INCOMPLETE synthetic gate: it ships a
# `violation_*` recall fixture but NO `clean_*` precision near-miss and NO
# sibling `*-gate.feature` self-AT. This is exactly the D-E meta-rule
# violation the meta-gate exists to catch: a gate shipped without its full
# golden-fixture set.
#
# The meta-gate's RECALL arm asserts that `orphan_gate` is correctly
# classified INCOMPLETE. If the meta-gate ever fails to flag this fixture,
# the meta-gate itself is vacuous and the recall arm reds.
__META_FIXTURE__ = True
