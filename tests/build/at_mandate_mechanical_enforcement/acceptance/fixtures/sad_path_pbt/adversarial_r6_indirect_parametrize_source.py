"""GOLDEN ADVERSARIAL FIXTURE (R6 self-dogfood) -- M11 gate.

This file is NOT a real test. It is the R6 self-dogfood adversarial case lifted
from the dormant ``scripts/cli/check_robustness_density.py`` (its
``RobustnessAdvisoryUnclassified`` / V4 case): a
``@pytest.mark.parametrize("x", _helper())`` whose value source is reached
through a helper Call -- a test-file AST shape the recast gate's own parser
cannot definitively classify (open vs finite cases).

Promoted to a golden adversarial fixture per the slice-07 spec: the gate's own
parser is the SUT here. The gate MUST survive this corpus DETERMINISTICALLY
WITHOUT CRASHING (no ``SyntaxError`` / ``AttributeError`` escaping the rule) --
it neither false-flags it as a PBT-layer violation (there is no ``@given`` /
stateful import) nor crashes on the indirect parametrize source. A gate that
crashes on its own adversarial corpus is itself the testing-theater it exists to
detect, one level down (R6 gate-self-dogfood).

The ``pytest`` symbol below is a stand-in so the corpus parses; the gate reads
structure, not behaviour.
"""

import pytest


def _failure_cases():
    # The indirect value source the gate's parser cannot statically enumerate.
    return [0, 1, 2]


@pytest.mark.parametrize("free_bytes", _failure_cases())
def test_install_failure_cases(free_bytes):
    # Example-based (NOT a @given / stateful PBT) -- the gate must NOT flag this
    # as a PBT-layer violation, and must NOT crash on the indirect parametrize
    # source the helper Call hides.
    assert free_bytes >= 0
