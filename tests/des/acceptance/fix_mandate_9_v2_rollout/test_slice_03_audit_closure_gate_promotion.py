"""pytest-bdd entry for fix-mandate-9-v2-rollout slice-03 acceptance ATs.

Mandate-13 — driving-port-only: this module imports ONLY the step bindings
package + the pytest-bdd `scenarios()` loader. ZERO direct-domain imports
from `des.domain.*` / `des.application.*` / `des.adapters.*` for the
purpose of invoking pure functions at the function boundary. The
composition root in `conftest.py` is the single driving-port surface; the
slice-03 SUTs are the retro-audit doc body, the carpaccio gate module's
new BLOCKING-mode detector symbol, and the project policy doc's new
`## Adapter Criticality` section.
"""

from pytest_bdd import scenarios

from .m9v2_rollout_steps.steps_slice_03 import *  # noqa: F403


scenarios("slice-03-audit-closure-gate-promotion.feature")
