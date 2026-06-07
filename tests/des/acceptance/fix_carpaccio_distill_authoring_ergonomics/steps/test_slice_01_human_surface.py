"""slice-01: the gate's human surface agrees with its verdict on a coupled clear.

ADR-002. Layer 3 (subprocess / FS acceptance) -- the real `des
carpaccio-slice-gate` CLI is the driving port (Mandate-13). Example-only, no PBT
(Mandate 9/11).

RED on master: the gate clears the coupled over-ceiling slice (exit 0) but its
human-surface line prints the refusal marker ("❌ FAIL -- carpaccio gate refused
(CoupledSliceAccepted)") instead of a PASS-class success. The AT reds on the
human-surface assertion -- a semantic AssertionError, not an import/collection
error.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from .steps_shared import *  # noqa: F403 -- shared step registry (S1 SSOT)


scenarios("../slice-01-human-surface-pass-class.feature")
