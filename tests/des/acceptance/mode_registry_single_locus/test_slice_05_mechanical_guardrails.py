"""pytest-bdd binding for mode-registry-single-locus slice-05.

Thin binding: registers the slice-05 scenarios and imports the step
vocabulary. No step definitions or business logic live here — the SSOT for
step bodies is `steps/steps_slice_05_mechanical_guardrails.py` +
`steps/composition_slice_05.py`; the SSOT for the scenarios is the `.feature`
file (per the DISTILL mandate).

Slice-05 = the GUARDRAIL: the three orthogonal, Python-only, git-free gates
(Layer A mode-locus-gate / Layer B mode-registry-completeness / Layer C
docgen --check resolver↔registry + registry↔runtime agreement) that make the
NEXT mode shotgun-surgery structurally impossible. Each gate is driven through
its REAL entry (`des <gate-id>` / `docgen --check`), each carries both teeth
(accept the clean baseline + refuse the planted defect naming it), and each
witnesses its own wiring (dispatcher-registry membership + catalog 1:1 mirror)
so no gate ships dormant.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from .steps.steps_slice_05_mechanical_guardrails import *


scenarios("slice-05-mechanical-guardrails.feature")
