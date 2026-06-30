"""pytest-bdd binding for des-spine-control-plane-ssot slice-03.

Thin binding: registers the slice-03 scenarios, imports the step vocabulary from
`steps.steps_slice_03_mode_resolution`, and provides the `mode_resolution_fixture`
composition-root service. No step definitions or business logic live here — the
SSOT for step bodies is the imported step module + the `ModeResolutionFixture`
composition; the SSOT for the scenarios is the `.feature` file (code is the SSOT,
per the DISTILL mandate).

Slice-03 = the mode-resolution SSOT (Class C): the spine resolves ONE workflow-mode
answer so the DELIVER dispatch (`des init-log`) and verify (`des verify-integrity`)
agree, and verify never hunts for a roadmap.json the active mode never wrote
(#65 dissolved, DDD-5/6/7). The `state` per-scenario scratchpad fixture is reused
from the slice-01 conftest (Mandate-12 step-reuse).
"""

from __future__ import annotations

import pytest
from pytest_bdd import scenarios

from .steps.composition_slice_03 import ModeResolutionFixture
from .steps.steps_slice_03_mode_resolution import *


@pytest.fixture
def mode_resolution_fixture(tmp_path) -> ModeResolutionFixture:
    """The single composition-root service all slice-03 step methods delegate to."""
    return ModeResolutionFixture(tmp_path)


scenarios("slice-03-mode-resolution.feature")
