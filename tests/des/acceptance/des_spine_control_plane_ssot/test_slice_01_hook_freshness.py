"""pytest-bdd binding for des-spine-control-plane-ssot slice-01.

Thin binding: registers the slice-01 scenarios and imports the step vocabulary
from `steps.steps_slice_01_hook_freshness`. No step definitions or business logic
live here — the SSOT for step bodies is the imported module; the SSOT for the
scenarios is the `.feature` file (code is the SSOT, per the DISTILL mandate).

Slice-01 = the walking skeleton: the DES spine hook hot path catches stale
installed code (#58) and names it LOUD while the session proceeds (degrade-loud).
The DV-2 "reaches-the-probe" assertion lives in AT-01 (the @walking_skeleton
scenario): it constructs the #58 topology (installed tree drifted from repo
source, project `.git/` present) and asserts the LOUD `install-freshness.stale`
warning is ACTUALLY EMITTED — not merely that the gate was called.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from .steps.steps_slice_01_hook_freshness import *  # noqa: F403  -- step vocabulary


scenarios("slice-01-hook-freshness-wiring.feature")
