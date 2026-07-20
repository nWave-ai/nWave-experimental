"""pytest-bdd binding for parallel-work-cleans-up-after-merge-back slice-01.

Thin binding: registers the slice-01 scenarios, imports the step vocabulary
from `steps.steps_slice_01_worktree_cleanup`, and re-exports the composition
fixtures (`cleanup_fixture`, `state_01`) so pytest discovers them for this
module's scenarios. No step definitions or business logic live here -- the
SSOT for step bodies is the imported steps module; the SSOT for the
scenarios is the `.feature` file (code is the SSOT, per the DISTILL
mandate).

Slice-01 = the walking skeleton (charter
`a-finished-parallel-unit-of-works-worktree-disappears-on-its-own.md`,
feature-delta Slice Plan row slice-01, Locked Decisions D-2/D-3,
ADR-SWARM-002): a confirmed-merged worktree is removed as a mechanical
consequence of that success, and a `--check-only` sweep refuses to call a
unit of work DONE while a merged worktree still lingers. RED today --
`des verify-worktree-cleanup` does not exist and is not a registered `des`
subcommand.
"""

from __future__ import annotations

from pytest_bdd import scenarios

# Re-export the composition fixtures so pytest discovers them for this module.
from .composition_slice_01 import (  # noqa: F401  -- pytest fixtures
    cleanup_fixture,
    state_01,
)
from .steps.steps_slice_01_worktree_cleanup import *


scenarios("slice-01-worktree-cleanup-on-confirmed-merge.feature")
