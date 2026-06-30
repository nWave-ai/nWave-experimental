"""pytest-bdd entry -- the readiness SUSTAINABILITY invariant (invariant 7) wiring.

Mandate-13 driving-port-only: imports ONLY the step-bindings module + the
pytest-bdd `scenarios()` loader. ZERO direct-domain imports. The driving port is
the real `des verify-readiness-pre-dispatch` subprocess (Layer 3) behind the
composition root.

atdd_pure active-RED: NO `@skip` marker. The must-block scenarios run and raise
`AssertionError` (at HEAD the gate ships six invariants only, so a
declared-but-missing/malformed sustainability section does NOT refuse readiness
and the `sustainability` invariant id never appears in the diagnostic). The
clear-path scenarios run and raise (the `sustainability` invariant never reports
`satisfied` because it does not yet exist). DELIVER adds the 7th invariant and
turns them all GREEN.
"""

from pytest_bdd import scenarios

from .readiness_sustainability_invariant_steps.steps_slice_07_sustainability_wiring import *


scenarios("slice-07-sustainability-wiring.feature")
