"""pytest-bdd binding for parallel-work-cleans-up-after-merge-back slice-03
(a bugfix's cleanup never waits on a feature-end it doesn't owe -- charter
`a-bugfixs-cleanup-never-waits-on-a-feature-end-it-doesnt-owe.md`, feature-
delta Slice Plan row slice-03, Locked Decisions D-4/D-5, ADR-SWARM-002).

Thin binding: registers the slice-03 scenarios, imports the 2 new Given
steps from `steps.steps_slice_03_feature_end_decoupling`, REUSES slice-01's
own When/Then vocabulary + `state_01` scratchpad fixture verbatim (Pillar 2
chained narrative), and wires this slice's own `cleanup_fixture` (constructs
`PendingFeatureEndFixture`, an EXTENSION of slice-01's
`WorktreeCleanupFixture`). No step definitions or business logic live here
-- the SSOT for step bodies is the imported steps modules; the SSOT for the
scenarios is the `.feature` file (code is the SSOT, per the DISTILL
mandate).

depends-on slice-01: reuses the SAME production mechanism (SHIPPED,
untracked pending its own COMMIT phase) -- this DISTILL pass is pipelined
during slice-01's A_GREEN per dispatch.
"""

from __future__ import annotations

from pytest_bdd import scenarios

# Reused verbatim from slice-01 (Pillar 2 chained narrative + step-reuse):
# the When/Then step vocabulary + the per-scenario scratchpad fixture. Never
# redefined here.
from .composition_slice_01 import state_01  # noqa: F401 -- pytest fixture
from .composition_slice_03 import cleanup_fixture  # noqa: F401 -- pytest fixture
from .steps.steps_slice_01_worktree_cleanup import *
from .steps.steps_slice_03_feature_end_decoupling import *


scenarios("slice-03-bugfix-cleanup-decoupled-from-feature-end.feature")
