"""pytest-bdd binding for autonomous-consolidation-and-bugfix-loops slice-01.

Thin binding: registers the slice-01 scenarios, imports the step vocabulary
from `steps.steps_slice_01_verdict_recovery`, and re-exports the composition
fixtures (`recovery_fixture`, `state_01`) so pytest discovers them for this
module's scenarios. No step definitions or business logic live here -- the
SSOT for step bodies is the imported steps module; the SSOT for the
scenarios is the `.feature` file (code is the SSOT, per the DISTILL
mandate).

Slice-01 = the walking skeleton (charter
`a-stale-closed-agent-recovers-its-own-verdict.md`, feature-delta Slice Plan
row slice-01, D-1/D-5/D-8): on every `StaleAgentClosed` emission (shipped,
`oss-spine-watchdog`) the spine parses the closed agent's own transcript for
its last-stated verdict and writes a PAIRED recovery record to the ledger in
the SAME tick. The close half is GREEN today (D-5 reuse); the paired
recovery half is RED today -- the generic atdd_pure return handler does not
parse transcripts for a verdict or emit any recovery record yet. GREEN once
DELIVER grafts the transcript-verdict-recovery emission alongside
`_maybe_emit_stale_agent_closed`.
"""

from __future__ import annotations

from pytest_bdd import scenarios

# Re-export the composition fixtures so pytest discovers them for this module.
from .composition_slice_01 import (  # noqa: F401  -- pytest fixtures
    recovery_fixture,
    state_01,
)
from .steps.steps_slice_01_verdict_recovery import *


scenarios("slice-01-stale-agent-verdict-recovery.feature")
