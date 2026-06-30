"""pytest-bdd binding for mode-registry-single-locus slice-02.

Thin binding: registers the slice-02 scenarios and imports the step
vocabulary. No step definitions or business logic live here — the SSOT for
step bodies is `steps/steps_slice_02_docgen_mode_projection.py` +
`steps/composition_slice_02.py`; the SSOT for the scenarios is the
`.feature` file (per the DISTILL mandate).

Slice-02 = the wiring witness for the slice-01 seam (faces (c)+(d) of the
mode 4-tuple): docgen projects the registry's `skill_load_set` into the
crafter spec's GENERATED region (retiring the :74 inline row) and the new
`descriptor` + `deliver_phase_shape` fields into the deliver guide's
GENERATED region — and the Layer-C staleness check refuses any projection
that drifted from its registry, instead of serving it stale.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from .steps.steps_slice_02_docgen_mode_projection import *


scenarios("slice-02-docgen-mode-projection.feature")
