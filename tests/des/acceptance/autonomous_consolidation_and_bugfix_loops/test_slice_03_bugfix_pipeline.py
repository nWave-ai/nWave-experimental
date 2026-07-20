"""pytest-bdd binding for autonomous-consolidation-and-bugfix-loops slice-03.

Thin binding: registers the slice-03 scenarios, imports the step vocabulary
from `steps.steps_slice_03_bugfix_pipeline`, and re-exports the composition
fixtures (`pipeline_fixture`, `state_03`) so pytest discovers them for this
module's scenarios. No step definitions or business logic live here -- the
SSOT for step bodies is the imported steps module; the SSOT for the
scenarios is the `.feature` file (code is the SSOT, per the DISTILL
mandate).

Slice-03 (charter `the-bugfix-loop-drains-the-queue-as-a-pipeline.md`,
feature-delta Slice Plan row slice-03, D-4/D-8): the bugfix loop drains the
defect queue as a two-lane pipeline -- cloud lanes (RCA, charter authoring,
AT authoring) fan out concurrently; the box lane (RED seal, crafter's GREEN
pass, Vera's examine, commit-slice) stays strictly serialized to one
in-flight item. Every scenario is RED today -- the driving port
(`des.cli.bugfix_pipeline_tick.main`) exists ONLY as a scaffold that reports
`PIPELINE_NOT_WIRED` and never touches the ledger; GREEN once DELIVER builds
the `des.domain.bugfix_pipeline` seam this scaffold lazily imports.
"""

from __future__ import annotations

from pytest_bdd import scenarios

# Re-export the composition fixtures so pytest discovers them for this module.
from .composition_slice_03 import (  # noqa: F401  -- pytest fixtures
    pipeline_fixture,
    state_03,
)
from .steps.steps_slice_03_bugfix_pipeline import *


scenarios("slice-03-bugfix-pipeline-drain.feature")
