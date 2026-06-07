"""pytest-bdd entry for fix-mandate-9-v2-rollout slice-01 acceptance ATs.

Mandate-13 — driving-port-only: this module imports ONLY the step bindings
package + the pytest-bdd `scenarios()` loader. ZERO direct-domain imports
from `des.domain.*` / `des.application.*` / `des.adapters.*` for the purpose
of invoking pure functions at the function boundary. The composition root
in `conftest.py` is the single driving-port surface.
"""

from pytest_bdd import scenarios

from .m9v2_rollout_steps.steps_slice_01 import *  # noqa: F403


scenarios("slice-01-detector-catalog-audit.feature")
