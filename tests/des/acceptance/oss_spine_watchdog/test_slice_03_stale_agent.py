"""pytest-bdd binding for oss-spine-watchdog slice-03.

Thin binding: registers the slice-03 scenarios, imports the step vocabulary from
`steps.steps_slice_03_stale_agent`, and re-exports the composition fixtures
(`stale_agent_fixture`, `state_03`) so pytest discovers them for this module's
scenarios. No step definitions or business logic live here — the SSOT for step
bodies is the imported steps module; the SSOT for the scenarios is the `.feature`
file (code is the SSOT, per the DISTILL mandate).

Slice-03 = the stale-agent timeout (#68 P2-E): on a returning atdd_pure agent the
SubagentStop hook computes the gap between the agent's last progress signal (the
AT-completion ledger's most-recent record `timestamp` for `(feature_id, slice_id)`)
and now; if the gap exceeds the threshold (DESIGN OQ-4 default 20 min) AND no
completed/blocked terminal exists for the key, it emits `StaleAgentClosed` — a
non-block INDETERMINATE naming the staleness + a durable ledger record — instead of
leaving the agent to hang (RCA root #68 instance #2). The terminal assertion lives
in AT-01 (RED today — the generic atdd_pure return handler does not read timestamps
or compute a staleness gap; GREEN once DELIVER grafts the gap check + threshold +
StaleAgentClosed emission into `_handle_atdd_pure_return`, DESIGN R-7). AT-02 (fresh
gap) + AT-03 (already-terminal) are the no-false-positive guardrail (GREEN today —
the never-close handler leaves a working / already-done agent alone, as it must).
"""

from __future__ import annotations

from pytest_bdd import scenarios

# Re-export the composition fixtures so pytest discovers them for this module.
from .composition_slice_03 import (  # noqa: F401  -- pytest fixtures
    stale_agent_fixture,
    state_03,
)
from .steps.steps_slice_03_stale_agent import *


scenarios("slice-03-stale-agent-timeout.feature")
