"""pytest-bdd entry for D4 Phase 3 slice-04 LogPersistencePort + adapters ATs.

Mandate-13 -- driving-port-only: this module imports ONLY the step bindings
package + the pytest-bdd `scenarios()` loader. ZERO direct-domain imports
from `des.domain.*` / `des.application.*` / `des.adapters.*` for the
purpose of invoking pure functions at the function boundary. The
composition root in `conftest.py` is the single driving-port surface; it
invokes `LogPersistencePort.emit(event)` -- the public Protocol method on
the adapter instance (Layer 3 in-process composition per the Layered Test
Discipline matrix, with real tmp_path filesystem reads for the
driven-internal ledger contract per the Architecture of Reference).
"""

from pytest_bdd import scenarios

from .dispatcher_steps.steps_log_persistence import *  # noqa: F403


scenarios("slice-04-log-persistence-port.feature")
