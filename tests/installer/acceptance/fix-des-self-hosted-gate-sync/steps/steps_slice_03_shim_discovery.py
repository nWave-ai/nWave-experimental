"""Step bodies for slice-03 shim-discovery-floor AT.

Layer: 3 (integration) — the step bodies invoke the production helper
`_discover_shims` directly against the real `src/des/cli/` directory. No
subprocess (the contract under test is a pure-function-shape glob +
set-membership check; spawning a subprocess would only add cost, no signal).
Per Mandate 11 this layer is example-based / parametrize-collapse; the AT
is a single concrete example (the closed-world invariant "discovery is a
superset of DES_SHIMS_FLOOR" needs no generative input space).

Mandate-12 SSOT (2026-05-18): every step body is ≤2 statements, ends in
`freshness_probe.<method>(...)`, contains no control flow. Business logic
lives in `FreshnessProbeFixture` (conftest.py) which delegates to the real
production helper (`scripts.install.plugins.des_plugin._discover_shims` +
`DES_SHIMS_FLOOR`). No new step decorators beyond the three Given/When/Then
this AT exercises — the discovery contract is a single observation.

Mandate 8: the universe-bound assertion at layer 3 is OPTIONAL (universe-
guard is a layer 1-3 requirement; layers 3+ may use traditional assertions
per the §"Layered Test Discipline" matrix). Applied here for consistency
with slice-01 / slice-02 step modules — universe is the single observable
`discovery.superset_of_floor: bool` plus the unchanged-preservation flag
on the source tree.
"""

from __future__ import annotations

import sys
from pathlib import Path


# Match the kebab-case workaround in the sibling conftest.py — inject the
# feature root so `from steps.domain_types import ...` and
# `from conftest import ...` resolve against THIS feature's local modules.
_FEATURE_ROOT = Path(__file__).resolve().parent.parent
if str(_FEATURE_ROOT) not in sys.path:
    sys.path.insert(0, str(_FEATURE_ROOT))

from pytest_bdd import given, then, when

from tests.common.state_delta import (
    assert_state_delta,
    set_to,
    unchanged,
)


# --- Universe (Mandate 8): port-exposed observables only -----------------
#
# Two universe entries:
#   - `discovery.superset_of_floor` — the load-bearing predicate the AT
#     asserts. True when `set(discovered) >= floor`.
#   - `source_tree.mtime_nano` — preservation observable proving the AT
#     does not mutate the production source tree it reads from
#     (`@contract-shape:unbounded-preservation`).

DISCOVERY_UNIVERSE = frozenset(
    {
        "discovery.superset_of_floor",
        "source_tree.mtime_nano",
    }
)


def _snapshot(state: dict) -> dict:
    """Build a dict snapshot of the universe from the scenario state.

    Pure function. Returns sentinels (None) for unobserved keys so the
    before-snapshot is well-defined before any discovery is invoked.
    """
    target = state.get("source_target")
    return {
        "discovery.superset_of_floor": state.get("superset_of_floor"),
        "source_tree.mtime_nano": (
            None if target is None or not target.exists() else target.stat().st_mtime_ns
        ),
    }


# --- Given ----------------------------------------------------------------

# Path to the production source tree the install plugin discovers from.
# Repo root = .../nWave-dev (this file lives 5 dirs deep under tests/...).
_REPO_ROOT = Path(__file__).resolve().parents[5]
_PROD_DES_CLI = _REPO_ROOT / "src" / "des" / "cli"


@given("the production source tree at `src/des/cli` is the discovery target")
def given_production_src_des_cli_is_discovery_target(state) -> None:
    state["source_target"] = _PROD_DES_CLI
    state["before"] = _snapshot(state)


# --- When -----------------------------------------------------------------


@when("the install plugin discovers shims from that directory")
def when_install_plugin_discovers_shims_from_that_directory(
    freshness_probe, state
) -> None:
    state["discovered"] = freshness_probe.discover_shims(state["source_target"])


# --- Then -----------------------------------------------------------------


@then("the discovered shims are a superset of the `DES_SHIMS_FLOOR` constant")
def then_discovered_shims_are_superset_of_floor(freshness_probe, state) -> None:
    state["floor"] = freshness_probe.discovery_floor()
    _assert_superset_observable(state)


@then("the production source tree is unchanged")
def then_production_source_tree_is_unchanged(state) -> None:
    after = _snapshot(state)
    assert_state_delta(
        before={"source_tree.mtime_nano": state["before"]["source_tree.mtime_nano"]},
        after={"source_tree.mtime_nano": after["source_tree.mtime_nano"]},
        universe=frozenset({"source_tree.mtime_nano"}),
        expected={"source_tree.mtime_nano": unchanged()},
    )


# --- Internal helpers (pure, no business logic) --------------------------


def _assert_superset_observable(state) -> None:
    """Universe-bound assertion that discovered ⊇ floor.

    Computes the boolean superset relation, stores it in scenario state,
    then asserts via state-delta that the universe entry transitioned from
    None (pre-discovery sentinel) to True with every other universe entry
    unchanged. Mandate 8 fail-closed: the universe-guard would catch
    accidental mutation of the source tree, etc.

    On AT failure, the AssertionError message lists the missing shims so a
    crafter can see at a glance which CLI modules dropped below the floor.
    """
    discovered = state["discovered"]
    floor = state["floor"]
    missing = floor - discovered
    state["superset_of_floor"] = not missing
    after = _snapshot(state)
    assert_state_delta(
        before={
            "discovery.superset_of_floor": state["before"][
                "discovery.superset_of_floor"
            ]
        },
        after={"discovery.superset_of_floor": after["discovery.superset_of_floor"]},
        universe=frozenset({"discovery.superset_of_floor"}),
        expected={"discovery.superset_of_floor": set_to(True)},
    )
    # Fail-closed sibling assertion: emit the diagnostic that names which
    # shim modules dropped below the floor when the state-delta passed
    # `set_to(True)` failed above. Reached only if the floor is missing
    # one or more modules from the discovery output.
    assert not missing, (
        f"discovery shortfall vs DES_SHIMS_FLOOR: missing={sorted(missing)!r}; "
        f"discovered={sorted(discovered)!r}; floor={sorted(floor)!r}"
    )
