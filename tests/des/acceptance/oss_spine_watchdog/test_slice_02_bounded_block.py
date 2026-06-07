"""pytest-bdd binding for oss-spine-watchdog slice-02.

Thin binding: registers the slice-02 scenarios, imports the step vocabulary from
`steps.steps_slice_02_bounded_block`, and re-exports the composition fixtures
(`bounded_block_fixture`, `state_02`) so pytest discovers them for this module's
scenarios. No step definitions or business logic live here — the SSOT for step
bodies is the imported steps module; the SSOT for the scenarios is the `.feature`
file (code is the SSOT, per the DISTILL mandate).

Slice-02 = the bounded-block terminal N=3: the DES spine counts prior identical
`SliceCommitBlocked` records for `(slice_id, pinned_commit_sha)` and, on the 3rd
identical block, terminates the agent loud with a non-block INDETERMINATE naming
the bound — instead of re-firing it forever (RCA root #68). The terminal assertion
lives in AT-01 (RED today — the block branch re-emits {decision:block}
unconditionally; GREEN once DELIVER threads pinned_commit_sha + adds the count
query + switches the block branch on the Nth identical block, DESIGN R-4/R-5/R-6).
AT-02 (new SHA) + AT-03 (different reason) are the progress-resets guardrail
(GREEN today — the always-block gate re-fires genuine progress, as it must).
"""

from __future__ import annotations

from pytest_bdd import scenarios

# Re-export the composition fixtures so pytest discovers them for this module.
from .composition_slice_02 import (  # noqa: F401  -- pytest fixtures
    bounded_block_fixture,
    state_02,
)
from .steps.steps_slice_02_bounded_block import *  # noqa: F403  -- step vocabulary


scenarios("slice-02-bounded-block-terminal.feature")
