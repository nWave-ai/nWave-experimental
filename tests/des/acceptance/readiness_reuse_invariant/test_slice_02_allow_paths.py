"""pytest-bdd entry -- slice-02 (ALLOW paths + degrade-LOUD INDETERMINATE).

Mandate-13 driving-port-only: imports ONLY the step-bindings package + the
pytest-bdd `scenarios()` loader. ZERO direct-domain imports. The driving port is
the real `des verify-readiness-pre-dispatch` subprocess (Layer 3) behind the
composition root.

atdd_pure active-RED: NO `@skip` marker. The clear-path scenarios run and raise
`AssertionError` (the 6th invariant does not yet exist, so it never appears as
`satisfied` in the diagnostic); the unreadable scenario runs and raises (the
gate today does not refuse on an unreadable delta via the reuse-first invariant
because that invariant is absent). DELIVER turns them GREEN.
"""

from pytest_bdd import scenarios

from .readiness_reuse_invariant_steps.steps_slice_02_allow_paths import *


scenarios("slice-02-allow-paths.feature")
