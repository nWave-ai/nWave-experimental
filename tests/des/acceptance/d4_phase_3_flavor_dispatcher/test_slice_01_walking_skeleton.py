"""pytest-bdd entry for D4 Phase 3 slice-01 walking-skeleton ATs.

Mandate-13 — driving-port-only: this module imports ONLY the step bindings
package + the pytest-bdd `scenarios()` loader. ZERO direct-domain imports
from `des.domain.*` / `des.application.*` / `des.adapters.*` for the purpose
of invoking pure functions at the function boundary. The composition root
in `conftest.py` is the single driving-port surface.
"""

from pytest_bdd import scenarios

from .dispatcher_steps.steps_dispatcher import *  # noqa: F403


scenarios("walking-skeleton.feature")
