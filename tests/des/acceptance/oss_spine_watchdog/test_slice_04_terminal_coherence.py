"""pytest-bdd binding for oss-spine-watchdog slice-04.

Thin binding: registers the slice-04 scenarios, imports the step vocabulary from
`steps.steps_slice_04_terminal_coherence`, and re-exports the composition fixtures
(`terminal_coherence_fixture`, `state_04`) so pytest discovers them for this
module's scenarios. No step definitions or business logic live here — the SSOT for
step bodies is the imported steps module; the SSOT for the scenarios is the
`.feature` file (code is the SSOT, per the DISTILL mandate).

Slice-04 = the terminal-coherence feature-end-fix the deep feature-end review
(`a360758f`, 2026-06-05) REJECTED the coherent feature on. The 3 prior slices each
ship correctly individually, but the DDD-5 terminating-INDETERMINATE wire-format
(non-block + loud stderr + DURABLE ledger record) was realized inconsistently. The
shared `_emit_terminating_indeterminate` EXTRACT makes every terminal honour DDD-5:

  * AT-01 (BLOCKER-2 / R-69-A, RED today) — the bounded-block terminal writes a
    durable SliceCommitBlockedTerminal record (today stderr-only, no record →
    re-read count delta 0).
  * AT-02 (BLOCKER-3 / R-69-B, RED today) — the cross-invocation stale check keys
    its no-double-close precondition on GENUINE terminals, so a stuck agent whose
    only prior record is a non-terminal SliceCommitBlocked re-fire record IS closed
    (today _EXISTING_TERMINAL_EVENTS includes SliceCommitBlocked → mistaken for a
    terminal → the stuck agent is wrongly left alone).
  * AT-03 (anti-vacuity, GREEN today, must stay GREEN) — an agent that already
    reached a genuine SliceCommitVerified terminal is NOT re-closed (the
    no-double-close precondition is preserved by the re-key, not dropped).
"""

from __future__ import annotations

from pytest_bdd import scenarios

# Re-export the composition fixtures so pytest discovers them for this module.
from .composition_slice_04 import (  # noqa: F401  -- pytest fixtures
    state_04,
    terminal_coherence_fixture,
)
from .steps.steps_slice_04_terminal_coherence import *  # noqa: F403  -- step vocab


scenarios("slice-04-terminal-coherence.feature")
