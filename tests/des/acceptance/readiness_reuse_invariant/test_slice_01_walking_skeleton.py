"""pytest-bdd entry -- slice-01 (@walking-skeleton refuse path).

Mandate-13 driving-port-only: imports ONLY the step-bindings package + the
pytest-bdd `scenarios()` loader. ZERO direct-domain imports. The composition
root in `conftest.py` is the single driving-port surface; it invokes the gate
via the real `des verify-readiness-pre-dispatch` subprocess (Layer 3).

atdd_pure active-RED: NO `@skip`/`@pending` marker. The four scenarios RUN and
raise `AssertionError` (the 6th invariant `reuse_first_or_design_skip` does not
yet exist, so the gate clears where the AT expects refused). DELIVER turns them
GREEN by adding the invariant; it does NOT unskip.
"""

from pytest_bdd import scenarios

from .readiness_reuse_invariant_steps.steps_slice_01_walking_skeleton import *


scenarios("slice-01-walking-skeleton.feature")
