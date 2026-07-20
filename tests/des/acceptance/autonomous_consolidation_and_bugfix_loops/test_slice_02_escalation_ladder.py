"""pytest-bdd binding for autonomous-consolidation-and-bugfix-loops slice-02.

Thin binding: registers the slice-02 scenarios, imports the step vocabulary
from `steps.steps_slice_02_escalation_ladder`, and re-exports the composition
fixtures (`escalation_fixture`, `state_02`) so pytest discovers them for this
module's scenarios. No step definitions or business logic live here -- the
SSOT for step bodies is the imported steps module; the SSOT for the
scenarios is the `.feature` file (code is the SSOT, per the DISTILL
mandate).

Slice-02 (charter `an-exhausted-loop-stops-instead-of-idle-holding.md`,
feature-delta Slice Plan row slice-02, D-2/D-8): a work-exhausted loop
escalates on the ratified 20/30/45-minute wall-clock ladder, anchored to
minutes-since-first-detected-exhausted, never to a tick count. Every scenario
is RED today -- the driving port
(`des.cli.work_exhausted_tick.main`) exists ONLY as a scaffold that reports
`LADDER_NOT_WIRED` and never touches the ledger; GREEN once DELIVER builds
the `des.domain.work_exhausted_ladder` seam this scaffold lazily imports.
"""

from __future__ import annotations

from pytest_bdd import scenarios

# Re-export the composition fixtures so pytest discovers them for this module.
from .composition_slice_02 import (  # noqa: F401  -- pytest fixtures
    escalation_fixture,
    state_02,
)
from .steps.steps_slice_02_escalation_ladder import *


scenarios("slice-02-work-exhausted-escalation-ladder.feature")
