"""pytest-bdd binding for many-features-close-for-one-full-suite slice-01
(a maintainer closes several ready features off one shared suite run --
charter `a-maintainer-closes-several-ready-features-off-one-shared-suite-run.md`,
feature-delta Slice Plan row slice-01, Locked Decisions D-1/D-3,
ADR-FEATURE-END-BATCH-001).

Thin binding: registers the slice-01 scenarios and imports the step
vocabulary from `steps.steps_slice_01_batch_run` + the `batch_fixture`/
`state_01` fixtures from `composition_slice_01`. No step definitions or
business logic live here -- the SSOT for step bodies is the imported steps
module; the SSOT for the scenarios is the `.feature` file (code is the SSOT,
per the DISTILL mandate).

S1 (step-text uniqueness): every literal step string in
`steps_slice_01_batch_run.py` is unique within this feature directory --
this is the feature's FIRST slice, so there is no sibling slice's vocabulary
to shadow yet.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from .composition_slice_01 import (  # noqa: F401 -- pytest fixtures
    batch_fixture,
    state_01,
)
from .steps.steps_slice_01_batch_run import *


scenarios("slice-01-batch-run-once-shared-suite.feature")
