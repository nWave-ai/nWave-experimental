"""pytest-bdd binding for des-spine-control-plane-ssot slice-05.

Thin binding: registers the slice-05 scenarios, imports the step vocabulary from
`steps.steps_slice_05_config_drift`, and provides the `config_drift_fixture`
composition-root service. No step definitions or business logic live here — the
SSOT for step bodies is the imported step module + the `ConfigDriftFixture`
composition; the SSOT for the scenarios is the `.feature` file (code is the SSOT,
per the DISTILL mandate).

Slice-05 = the config-asset drift envelope (SYS-4 / AD-27, the binding R1 ToC
constraint closer): the freshness gate's envelope widens from `*.py`-only to the
shipped `lib/nWave/` config assets, so a drifted `flavors/atdd_pure.yaml` (the
gate-composition SSOT slice-04 made authoritative) is caught + named LOUD instead
of drifting silently. The `state` per-scenario scratchpad fixture is reused from
the slice-01 conftest (Mandate-12 step-reuse).
"""

from __future__ import annotations

import pytest
from pytest_bdd import scenarios

from .steps.composition_slice_05 import ConfigDriftFixture
from .steps.steps_slice_05_config_drift import *  # noqa: F403  -- vocab


@pytest.fixture
def config_drift_fixture(tmp_path) -> ConfigDriftFixture:
    """The single composition-root service all slice-05 step methods delegate to."""
    return ConfigDriftFixture(tmp_path)


scenarios("slice-05-config-drift.feature")
