"""Pytest-bdd bindings for slice-02 install-manifest-write scenarios.

One `@scenario` shell per Gherkin scenario in
`slice-02-install-manifest-write.feature`. Scenario Outlines emit one test
per Examples row at collection time, so the two Outlines (3 rows each) +
1 standalone scenario yield 7 ATs.

The shells import the sibling `steps/steps_slice_02_install_manifest.py`
module so its `@given`, `@when`, `@then` decorators register before
pytest-bdd resolves the scenarios.

Pattern source: `test_slice_01_walking_skeleton.py` — same kebab-case
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

from pytest_bdd import scenario

# Register the step decorators by importing the steps module. The name
# `_slice_02_steps` keeps the import non-discardable by linters and signals
# "this is a registration-side-effect import".
from steps import steps_slice_02_install_manifest as _slice_02_steps  # noqa: F401


@scenario(
    "slice-02-install-manifest-write.feature",
    "Install plugin writes a schema-v1 manifest for each source kind",
)
def test_slice_02_install_writes_schema_v1_manifest_for_each_source_kind() -> None:
    """AT-02-A: parametrize over (dev-checkout | pre-built | wheel) — 3 rows.

    Each row asserts the manifest is present, schema_version=1, source_kind
    matches the input, and tree_hash matches the §1.6 recomputed hash.
    """


@scenario(
    "slice-02-install-manifest-write.feature",
    "After a fresh install the gate proceeds for the dev checkout",
)
def test_slice_02_gate_proceeds_for_dev_checkout_after_install() -> None:
    """AT-02-B: post-install `import des.cli` PROCEEDs with state C."""


@scenario(
    "slice-02-install-manifest-write.feature",
    "Mutating a representative installed file makes the gate REFUSE state D",
)
def test_slice_02_gate_refuses_state_d_after_file_mutation() -> None:
    """AT-02-C: parametrize over (freshness.py | run_contract_gate.py |
    repo_source_probe.py) — 3 rows. Each row mutates one installed file
    and asserts the gate REFUSEs with state D citing the diverged file.

    Architect's original slice plan tagged this PBT (`@given(file_to_mutate)`);
    DISTILL applied the Mandate-11 layer-3 downgrade to parametrize-collapse
    over 3 representative files (one runtime, one CLI, one adapter).
    """
