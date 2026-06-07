"""pytest-bdd binding for oss-spine-watchdog slice-06.

Thin binding: registers the slice-06 scenarios, imports the step vocabulary from
`steps.steps_slice_06_timeout_countability`, and re-exports the composition fixtures
(`timeout_countability_fixture`, `state_06`) so pytest discovers them for this
module's scenarios. No step definitions or business logic live here — the SSOT for
step bodies is the imported steps module; the SSOT for the scenarios is the
`.feature` file (code is the SSOT, per the DISTILL mandate).

Slice-06 = the timeout-block countability fix; it closes residue R-69-F of the
feature-end deep review (`a01511d9`): the G_COMMIT exit-gate handler's `except
subprocess.TimeoutExpired` path emits a FIELDLESS `SliceCommitBlocked` that
`count_slice_commit_blocked` (keyed on `(slice_id, pinned_commit_sha,
block_reason)`) can NEVER match → a timeout-driven re-fire loop on the same commit is
UNCOUNTABLE → the slice-02 N=3 bound is defeated for timeout-originated blocks.
Slice-06 EXTENDs the timeout emit to thread `pinned_commit_sha` +
`block_reason="gate-timeout"`:

  * AT-01 (R-69-F, RED today) — the 3rd identical `(slice, sha, "gate-timeout")`
    block (2 seeded priors + 1 forced timeout) leaves a durable terminal record and
    a non-block return. RED today (the fieldless emit never matches the priors →
    count 0 → re-fire); GREEN once the timeout emit threads the fields.
  * AT-02 (anti-vacuity discriminator, GREEN today, must stay GREEN) — a single
    timeout with no priors takes the ordinary block path; the bounded-block terminal
    does NOT fire (a count-blind fix that always-terminated would wrongly close this
    single timeout).
"""

from __future__ import annotations

from pytest_bdd import scenarios

# Re-export the composition fixtures so pytest discovers them for this module.
from .composition_slice_06 import (  # noqa: F401  -- pytest fixtures
    state_06,
    timeout_countability_fixture,
)
from .steps.steps_slice_06_timeout_countability import *  # noqa: F403  -- step vocab


scenarios("slice-06-timeout-block-countability.feature")
