"""Pytest-bdd binding for slice-05 manifest-corruption-DEGRADED ATs.

One `@scenario` shell — slice-05 is a single Scenario Outline with 4
Examples rows (one per enumerable corruption kind). pytest-bdd collects
one parametrized test per row.

The shell imports the sibling `steps/steps_slice_05_manifest_corruption.py`
module so its `@given` and `@then` decorators register before pytest-bdd
resolves the scenarios. Slice-01 / slice-02 step modules are also implicitly
loaded by the feature-root conftest, registering the SSOT step phrases
slice-05 reuses (the `import des.cli`-When, the `REFUSES exit 78`-Then, and
the `gate reports state {state_letter}`-Then for DEGRADED).

Pattern source: `test_slice_04_optout_grid.py` — same kebab-case feature
directory convention.
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
# `_slice_05_steps` keeps the import non-discardable by linters and signals
# "this is a registration-side-effect import".
from steps import (
    steps_slice_05_manifest_corruption as _slice_05_steps,  # noqa: F401
)


@scenario(
    "slice-05-degraded-manifest-corruption.feature",
    "A malformed install manifest is REFUSED as DEGRADED per kind",
)
def test_slice_05_malformed_manifest_refused_as_degraded() -> None:
    """AT-05-A: 4-row Scenario Outline over manifest corruption kinds.

    Corruption kinds: {unknown_schema_version, missing_required_field,
    non_json_content, empty_file}. Coupled per ADR-028 D2-bis (same SUT
    classifier method `RepoSourceProbe._read_install_manifest` with
    bounded-change varying inputs). pytest-bdd collects one parametrized
    test per Examples row.

    Mandate 11: layer-3 sad paths are enumerated examples (no PBT — the
    corruption shapes form a closed enumerable set; PBT on a real-I/O
    subprocess test buys no signal).
    """
