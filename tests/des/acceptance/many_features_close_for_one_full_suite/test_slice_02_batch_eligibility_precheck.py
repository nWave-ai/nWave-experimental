"""pytest-bdd binding for many-features-close-for-one-full-suite slice-02
(batch-eligibility precheck -- charter
`a-batch-with-one-not-ready-feature-refuses-as-a-whole.md`, feature-delta
Slice Plan row slice-02, Locked Decision D-5, D-D7, depends-on slice-01).

Converted from an initial pytest-only draft: the carpaccio entry-gate
enforces ONE AT-discovery mode per feature, and slice-01 already SHIPPED a
Gherkin `.feature` (`slice-01-batch-run-once-shared-suite.feature`) --
this feature is Gherkin-mode, so slice-02 must be too.

Thin binding: registers the slice-02 scenarios and imports the step
vocabulary from `steps.steps_slice_02_batch_eligibility` + the
`eligibility_fixture`/`state_02` fixtures from `composition_slice_02`. No
step definitions or business logic live here -- the SSOT for step bodies is
the imported steps module; the SSOT for the scenarios is the `.feature`
file (code is the SSOT, per the DISTILL mandate).

S1 (step-text uniqueness): every literal step string in
`steps_slice_02_batch_eligibility.py` is DISTINCT from slice-01's own
vocabulary (`steps_slice_01_batch_run.py`) -- verified by inspection; in
particular the `When` step text differs (slice-02 observes raw json-lines
via `run_batch_and_collect_lines`, slice-01 observes a typed
`BatchRunOutcome` via `run_batch_in_process`).
"""

from __future__ import annotations

from pytest_bdd import scenarios

from .composition_slice_02 import (  # noqa: F401 -- pytest fixtures
    eligibility_fixture,
    state_02,
)
from .steps.steps_slice_02_batch_eligibility import *


scenarios("slice-02-batch-eligibility-precheck.feature")
