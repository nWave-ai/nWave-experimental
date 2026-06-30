"""pytest-bdd binding for mode-registry-single-locus slice-01.

Thin binding: registers the slice-01 scenarios and imports the step
vocabulary. No step definitions or business logic live here — the SSOT for
step bodies is `steps/steps_slice_01_registry_skill_load_set.py` +
`steps/composition_slice_01.py`; the SSOT for the scenarios is the
`.feature` file (per the DISTILL mandate).

Slice-01 = the walking-skeleton vertical of the mode registry (face (c) of
the mode 4-tuple): the crafter's conditional skills are answered by the
active flavor's `skill_load_set` registry entry — byte-identical to the
inline table the agent spec carried — and a registry that does not properly
declare the entry is refused, never improvised around.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from .steps.steps_slice_01_registry_skill_load_set import *


scenarios("slice-01-registry-skill-load-set.feature")
