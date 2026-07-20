"""pytest-bdd binding for autonomous-consolidation-and-bugfix-loops slice-04.

Thin binding: registers the slice-04 scenarios, imports the step vocabulary
from `steps.steps_slice_04_consolidation_intake`, and re-exports the
composition fixtures (`intake_fixture`, `state_04`) so pytest discovers them
for this module's scenarios. No step definitions or business logic live
here -- the SSOT for step bodies is the imported steps module; the SSOT for
the scenarios is the `.feature` file (code is the SSOT, per the DISTILL
mandate).

Slice-04 (charter
`trunk-health-signals-become-queue-items-that-never-vanish.md`, feature-delta
Slice Plan row slice-04, D-4/D-19): a detected trunk-health signal (drift /
un-merged work / stale branch / failing gate) becomes exactly one queue item
by entering the SAME shared pipeline slice-03 built. Every scenario is RED
today -- the driving port (`des.cli.consolidation_signal_tick.main`) exists
ONLY as a scaffold that reports `CONSOLIDATION_INTAKE_NOT_WIRED` and never
touches the ledger; GREEN once DELIVER builds the
`des.domain.consolidation_queue_intake` seam this scaffold lazily imports.
"""

from __future__ import annotations

from pytest_bdd import scenarios

# Re-export the composition fixtures so pytest discovers them for this module.
from .composition_slice_04 import (  # noqa: F401  -- pytest fixtures
    intake_fixture,
    state_04,
)
from .steps.steps_slice_04_consolidation_intake import *


scenarios("slice-04-trunk-health-signals-become-queue-items.feature")
