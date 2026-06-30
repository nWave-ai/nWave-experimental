"""pytest-bdd entry for D4 Phase 3 slice-05 multi-gate dispatch.pre wire ATs.

Mandate-13 -- driving-port-only: this module imports ONLY the step bindings
package + the pytest-bdd `scenarios()` loader. ZERO direct-domain imports
from `des.domain.*` / `des.application.*` / `des.adapters.*` for the purpose
of invoking pure functions at the function boundary. The composition root
in `conftest.py` is the single driving-port surface; the slice-05
`MultiGateWireComposition` invokes `evaluate_atdd_pure_dispatch(...)` via
the public driving-port surface inherited from slice-02 (same public
function, same return shape; the refactor is internal to `_gate_invoker_for`
which step bodies never touch).
"""

from pytest_bdd import scenarios

from .dispatcher_steps.steps_multi_gate_wire import *


scenarios("slice-05-multi-gate-wire.feature")
