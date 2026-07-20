"""pytest-bdd binding for autonomous-consolidation-and-bugfix-loops slice-05.

Thin binding: registers the slice-05 scenarios, imports the step vocabulary
from `steps.steps_slice_05_session_start_wiring`, and re-exports the
composition fixtures (`loop_tick_wiring_fixture`, `state_05`) so pytest
discovers them for this module's scenarios. No step definitions or business
logic live here -- the SSOT for step bodies is the imported steps module; the
SSOT for the scenarios is the `.feature` file (code is the SSOT, per the
DISTILL mandate).

Slice-05 resolves feature-delta Open Question OQ-3 (DA-13): slices 02-04
shipped three correct, ledger-safe driving ports with ZERO production
callers. This slice wires them into `handle_session_start()` -- mirrors
slice-01's already-shipped SubagentStop pattern
(`_maybe_emit_stale_agent_closed`). RED today -- `handle_session_start()`
does not yet read any `.nwave/loop-tick-*.json` request file; GREEN once
DELIVER grafts the three distinctly-named wrapper calls
(`_maybe_tick_work_exhausted` / `_maybe_tick_bugfix_pipeline` /
`_maybe_tick_consolidation_intake` -- none of them `_stabilize_tick`, the
extension point `background-loops-hybrid-c` separately reserves in the same
hook function; see `steps/domain_types_slice_05.py` § HOOK-POINT
COEXISTENCE).
"""

from __future__ import annotations

from pytest_bdd import scenarios

# Re-export the composition fixtures so pytest discovers them for this module.
from .composition_slice_05 import (  # noqa: F401  -- pytest fixtures
    loop_tick_wiring_fixture,
    state_05,
)
from .steps.steps_slice_05_session_start_wiring import *


scenarios("slice-05-session-start-loop-tick-wiring.feature")
