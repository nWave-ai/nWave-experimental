"""pytest-bdd entry for D4 Phase 3 slice-03 D1 readiness pre-dispatch gate ATs.

Mandate-13 -- driving-port-only: this module imports ONLY the step bindings
package + the pytest-bdd `scenarios()` loader. ZERO direct-domain imports
from `des.domain.*` / `des.application.*` / `des.adapters.*` for the purpose
of invoking pure functions at the function boundary. The composition root
in `conftest.py` is the single driving-port surface; it invokes the gate
via subprocess (Layer 3 subprocess per the Layered Test Discipline matrix).

Module-level skip marker -- per friction #57 invariant 5 (PreCommitScopeUnsatisfiable):
RED scaffold tests stay skipped at the module level so pre-commit pytest scope
remains satisfiable. The DELIVER crafter unskips the marker (or removes it)
inside the A_GREEN_ATS phase as each scenario goes GREEN against the
implemented gate.
"""

from pytest_bdd import scenarios

from .dispatcher_steps.steps_readiness_gate import *  # noqa: F403


scenarios("slice-03-d1-readiness-gate.feature")
