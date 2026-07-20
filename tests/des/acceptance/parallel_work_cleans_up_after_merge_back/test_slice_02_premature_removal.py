"""pytest-bdd binding for parallel-work-cleans-up-after-merge-back slice-02
(an attempt to remove a worktree before its merge-back is confirmed is
refused -- charter
`removing-a-worktree-before-its-merge-is-confirmed-is-refused.md`, feature-
delta Slice Plan row slice-02, Locked Decision D-3, ADR-SWARM-002).

Thin binding: registers the slice-02 scenarios, imports the step vocabulary
from `steps.steps_slice_02_premature_removal`, REUSES slice-01's own
`given_worktree_with_branch_state` Given step + `state_01` scratchpad
fixture verbatim (Pillar 2 chained narrative), and wires this slice's own
`cleanup_fixture` (constructs `PrematureRemovalFixture`, an EXTENSION of
slice-01's `WorktreeCleanupFixture` -- D-D4 "zero new plumbing", Test Reuse
& Consolidation note in the feature-delta). No step definitions or business
logic live here -- the SSOT for step bodies is the imported steps modules;
the SSOT for the scenarios is the `.feature` file (code is the SSOT, per the
DISTILL mandate).

depends-on slice-01: same RED reason as slice-01 (`verify-worktree-cleanup`
is mid-A_GREEN, this DISTILL pass is pipelined during slice-01's own
A_GREEN per dispatch).
"""

from __future__ import annotations

from pytest_bdd import scenarios

# Reused verbatim from slice-01 (Pillar 2 chained narrative + step-reuse):
# the Given step + its typed-parameter phrase validation, and the per-
# scenario scratchpad fixture. Never redefined here.
from .composition_slice_01 import state_01  # noqa: F401 -- pytest fixture
from .composition_slice_02 import cleanup_fixture  # noqa: F401 -- pytest fixture
from .steps.steps_slice_01_worktree_cleanup import *
from .steps.steps_slice_02_premature_removal import *


scenarios("slice-02-premature-removal-refused.feature")
