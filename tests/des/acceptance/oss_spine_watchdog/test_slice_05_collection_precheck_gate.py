"""pytest-bdd binding for oss-spine-watchdog slice-05.

Thin binding: registers the slice-05 scenarios, imports the step vocabulary from
`steps.steps_slice_05_collection_precheck_gate`, and re-exports the composition
fixtures (`collection_precheck_gate_fixture`, `state_05`) so pytest discovers them
for this module's scenarios. No step definitions or business logic live here — the
SSOT for step bodies is the imported steps module; the SSOT for the scenarios is the
`.feature` file (code is the SSOT, per the DISTILL mandate).

Slice-05 = the LAST slice; it closes BLOCKER-1 of the deep feature-end review
(`a360758f`, 2026-06-05): slice-01 shipped the collection-precheck PROBE
(`run_contract_gate --collect-only`) but the G_COMMIT exit-gate handler NEVER CALLS
it, so a real collection crash on the live spine STILL re-fires the crafter (the #68
loop the walking-skeleton exists to kill, NOT killed on the production hot path).
Slice-05 EXTENDs `_handle_g_commit_exit_gate` to run the no-skip collection precheck
BEFORE E2 and terminate via the slice-04 shared `_emit_terminating_indeterminate`:

  * AT-01 (BLOCKER-1 / R-69-D, RED today) — a real collection crash leaves a durable
    terminal ledger record (today no precheck → the crash re-blocks → a
    SliceCommitBlocked re-fire record, NOT a terminal → genuine-terminal delta 0).
  * AT-02 (BLOCKER-1 / R-69-D, RED today) — the collection terminal is NON-block, so
    the harness reaches a Stop and the crafter is NOT re-fired (today the crash
    re-blocks → `{decision:block}` → re-fire).
  * AT-03 (anti-vacuity discriminator, GREEN today, must stay GREEN) — a
    cleanly-collecting commit that fails E1/E2 for an ordinary reason takes the
    ordinary block path; the collection terminal does NOT fire (a collection-blind
    precheck that always-terminated would wrongly close this clean commit).
"""

from __future__ import annotations

from pytest_bdd import scenarios

# Re-export the composition fixtures so pytest discovers them for this module.
from .composition_slice_05 import (  # noqa: F401  -- pytest fixtures
    collection_precheck_gate_fixture,
    state_05,
)
from .steps.steps_slice_05_collection_precheck_gate import *  # noqa: F403  -- step vocab


scenarios("slice-05-collection-precheck-gate.feature")
