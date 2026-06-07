"""Pytest-bdd bindings for slice-01 walking-skeleton scenarios.

One `@scenario` shell per Gherkin scenario in
`slice-01-freshness-gate-walking-skeleton.feature`. The shells import the
sibling `steps/steps_slice_01_walking_skeleton.py` module so its `@given`,
`@when`, `@then` decorators register before the bindings execute.

Pattern source: tests/installer/acceptance/backup-retention-policy/
test_walking_skeleton.py — the kebab-case feature directory convention.

This file MUST be `test_*.py` to satisfy pytest's default `python_files`
discovery; the sibling `steps_*.py` modules are imported here, never
collected directly.
"""

from __future__ import annotations

import sys
from pathlib import Path


# Mirror the kebab-case sys.path workaround from conftest.py so the steps
# module's local imports (`from steps.domain_types import ...`, `from
# conftest import ...`) resolve.
_FEATURE_ROOT = Path(__file__).resolve().parent
if str(_FEATURE_ROOT) not in sys.path:
    sys.path.insert(0, str(_FEATURE_ROOT))

from pytest_bdd import scenario  # noqa: E402

# Register the step decorators by importing the steps module. The name
# `_slice_01_steps` keeps the import non-discardable by linters and signals
# "this is a registration-side-effect import".
from steps import steps_slice_01_walking_skeleton as _slice_01_steps  # noqa: E402, F401


@scenario(
    "slice-01-freshness-gate-walking-skeleton.feature",
    "Operator runs a CLI against an installed tree without manifest",
)
def test_slice_01_gate_refuses_when_no_manifest() -> None:
    """AT 01-A: DEGRADED state refuses with exit 78."""


@scenario(
    "slice-01-freshness-gate-walking-skeleton.feature",
    "Customer install on a host with no repository PROCEEDS silently",
)
def test_slice_01_gate_proceeds_for_customer_no_repo() -> None:
    """AT 01-B: state A (customer) proceeds silently — F3 bootstrap-blind anchor."""


@scenario(
    "slice-01-freshness-gate-walking-skeleton.feature",
    "Operator opts out via NWAVE_FRESHNESS=skip and the gate honors the bypass",
)
def test_slice_01_gate_honors_skip_opt_out_when_no_manifest() -> None:
    """AT 01-C: NWAVE_FRESHNESS=skip bypasses DEGRADED-no-manifest.

    F3 bootstrap-blind closure for repo's dev-tree usage and the install
    plugin's own verification probes. Scope-expansion from slice-03 per
    Crafter-A escalation 2026-05-23, ratified by Ale (option A).
    """
