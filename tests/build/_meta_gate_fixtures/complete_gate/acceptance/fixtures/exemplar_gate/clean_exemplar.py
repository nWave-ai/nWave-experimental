# Meta-gate planted fixture (complete_gate, PRECISION near-miss control).
#
# A synthetic gate dir that DOES satisfy the D-E golden-fixture meta-rule:
# it carries a `clean_*` precision near-miss + a `violation_*` recall fixture
# AND a sibling self-AT `.feature`. The meta-gate MUST classify this gate as
# COMPLETE — proving the meta-gate does not false-positive on a well-formed
# gate (precision arm).
__META_FIXTURE__ = True
