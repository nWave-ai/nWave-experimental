"""Pytest-bdd binding for slice-03 shim-discovery-floor AT.

One `@scenario` shell — slice-03 is a single example-based AT (the closed-
world superset invariant needs no parametrize / no PBT, per Mandate 11 +
the SPLIT rationale in feature-delta §5 slice 03).

The shell imports the sibling `steps/steps_slice_03_shim_discovery.py`
module so its `@given`, `@when`, `@then` decorators register before
pytest-bdd resolves the scenario.

Pattern source: `test_slice_02_install_manifest.py` — same kebab-case
feature directory convention.
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
# `_slice_03_steps` keeps the import non-discardable by linters and signals
# "this is a registration-side-effect import".
from steps import steps_slice_03_shim_discovery as _slice_03_steps  # noqa: E402, F401


@scenario(
    "slice-03-shim-discovery-floor.feature",
    "Discovery returns a superset of the DES_SHIMS_FLOOR regression constant",
)
def test_slice_03_discovery_returns_superset_of_floor() -> None:
    """AT-03-A: `_discover_shims(src/des/cli)` ⊇ `DES_SHIMS_FLOOR`.

    Layer-3 integration AT — invokes the production helper directly on the
    real `src/des/cli/` directory. Single example, no parametrize, no PBT
    (per Mandate 11 + closed-world finite invariant).

    Drift-across-boundary (F1) closure: the filesystem is the SSOT for
    shim enumeration; `DES_SHIMS_FLOOR` is the frozen regression floor
    that cannot silently shrink without reding this AT.
    """
