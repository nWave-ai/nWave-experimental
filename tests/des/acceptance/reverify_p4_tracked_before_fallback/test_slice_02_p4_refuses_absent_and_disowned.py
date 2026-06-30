"""slice-02 binder: P4 refuses never-authored and tag-dropped-by-commit.

Two refusal states parametrize-collapsed via the Scenario Outline -- bounded,
enumerable AT-presence domain (Mandate 9/11: layer-3 example-based, no PBT).

These two scenarios are EXPECTED GREEN even before the fix: P4's current
strict-touch behaviour already refuses both states. They are guard ATs --
they pin that the slice-01 fallback does not regress them into a blanket
accept. DELIVER must keep them green while making slice-01 go green.
"""

from pytest_bdd import scenarios

# Step definitions -- shared vocabulary (Mandate 10 / Mandate-12).
from .steps.steps_reverify_p4 import *


scenarios("slice_02_p4_refuses_absent_and_disowned.feature")
