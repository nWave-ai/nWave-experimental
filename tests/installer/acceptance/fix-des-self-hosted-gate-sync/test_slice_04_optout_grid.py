"""Pytest-bdd bindings for slice-04 NWAVE_FRESHNESS opt-out grid scenarios.

Two `@scenario` shells — one for the Scenario Outline (6 cartesian rows
collapsed via parametrize per ADR-028 D2-bis coupled justification) and one
for the named unknown-value sad path.

The shells import the sibling `steps/steps_slice_04_optout_grid.py` module
so its `@given`, `@when`, `@then` decorators register before pytest-bdd
resolves the scenarios. Slice-01 / slice-02 step modules are also implicitly
loaded by the feature-root conftest, registering the SSOT step phrases
slice-04 reuses (the `import des.cli`-When and the `gate reports state`-Then).

Pattern source: `test_slice_02_install_manifest.py` + `test_slice_03_shim_discovery.py`
— same kebab-case feature directory convention.
"""

from __future__ import annotations

import sys
from pathlib import Path


# Mirror the kebab-case sys.path workaround from conftest.py so the steps
# module's local imports (`from steps.domain_types import ...`) resolve.
_FEATURE_ROOT = Path(__file__).resolve().parent
if str(_FEATURE_ROOT) not in sys.path:
    sys.path.insert(0, str(_FEATURE_ROOT))

from pytest_bdd import scenario  # noqa: E402

# Register the step decorators by importing the steps module. The name
# `_slice_04_steps` keeps the import non-discardable by linters and signals
# "this is a registration-side-effect import".
from steps import steps_slice_04_optout_grid as _slice_04_steps  # noqa: E402, F401


@scenario(
    "slice-04-optout-grid-remaining.feature",
    "NWAVE_FRESHNESS opt-out grid behaviour matches §1.8",
)
def test_slice_04_optout_grid_behaviour_matches_spec() -> None:
    """AT-04-A: 6-row Scenario Outline over (install_state × opt_out).

    Cartesian: {fresh, stale} × {enforce, verbose, empty}. Coupled per
    ADR-028 D2-bis (same SUT method `assert_fresh_or_explain` honoring
    NWAVE_FRESHNESS with bounded-change varying inputs). pytest-bdd
    collects one parametrized test per Examples row.
    """


@scenario(
    "slice-04-optout-grid-remaining.feature",
    "NWAVE_FRESHNESS with an unknown value is REFUSED as DEGRADED",
)
def test_slice_04_unknown_optout_value_is_refused_as_degraded() -> None:
    """AT-04-B: an unrecognised NWAVE_FRESHNESS value refuses with exit 78.

    Mandate 11: layer-3 sad path is an enumerated example (no PBT). Coupled
    with AT-04-A's outline via ADR-028 D2-bis — both exercise the same
    SUT method's input vocabulary (the env var's value space).
    """
