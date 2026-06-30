"""Step bodies for slice-02 install-manifest-write ATs.

Layer: 3 (subprocess + real install plugin against tmp_path) — per Mandate 11
this layer is example-only / parametrize-collapse; sad paths (state D mutation)
are enumerated as a Scenario Outline over `mutated_file`, NEVER PBT-generated.
The architect's slice plan §5 originally tagged AT-02-C as PBT — that PBT
downgrade was applied by DISTILL when scoping to subprocess layer (Mandate 9).

Mandate-12: every step body is ≤2 statements, ends in
`freshness_probe.<method>(...)`, contains no control flow. Business logic
lives in `FreshnessProbeFixture` (conftest.py) which delegates to the real
`DESPlugin._install_des_module` composition root.

Mandate 8: assertions go through `assert_state_delta(before, after, universe,
expected)` from `tests.common.state_delta`. Two universes are declared:

    INSTALL_UNIVERSE — observables of the just-installed tree (manifest
        presence, schema_version, source_kind, tree_hash equality with the
        recomputed hash). All port-exposed; nothing about install plugin
        internals appears.

    GATE_UNIVERSE — observables of a subsequent `import des.cli` spawn (exit
        code, verdict). Shared with slice-01 step module by intent.
"""

from __future__ import annotations

import sys
from pathlib import Path


# Match the kebab-case workaround in the sibling conftest.py — inject the
# feature root so `from steps.domain_types import ...` and `from conftest
# import ...` resolve against THIS feature's local modules.
_FEATURE_ROOT = Path(__file__).resolve().parent.parent
if str(_FEATURE_ROOT) not in sys.path:
    sys.path.insert(0, str(_FEATURE_ROOT))

from pytest_bdd import given, parsers, then, when
from steps.domain_types import (
    FreshnessOptOut,
    FreshnessState,
    SourceTreeKind,
)

from tests.common.state_delta import (
    assert_state_delta,
    set_to,
)


# --- Universe (Mandate 8): port-exposed observables only -----------------

INSTALL_UNIVERSE = frozenset(
    {
        "installed.manifest_present",
        "installed.manifest.schema_version",
        "installed.manifest.source_kind",
        "installed.manifest.tree_hash_matches_recomputed",
    }
)

GATE_UNIVERSE = frozenset(
    {
        "outcome.exit_code",
        "outcome.verdict",
        "outcome.stderr_state",
    }
)


def _install_snapshot(state: dict) -> dict:
    """Build a dict snapshot of the INSTALL universe from scenario state.

    Pure function. Returns sentinels (None) for unobserved keys so the
    before-snapshot is well-defined before any install completes.
    """
    installed = state.get("installed")
    manifest = getattr(installed, "manifest", None)
    return {
        "installed.manifest_present": (
            None if installed is None else manifest is not None
        ),
        "installed.manifest.schema_version": getattr(manifest, "schema_version", None),
        "installed.manifest.source_kind": getattr(manifest, "source_kind", None),
        "installed.manifest.tree_hash_matches_recomputed": state.get(
            "manifest_tree_hash_matches_recomputed"
        ),
    }


def _gate_snapshot(state: dict) -> dict:
    """Build a dict snapshot of the GATE universe from scenario state."""
    outcome = state.get("outcome")
    return {
        "outcome.exit_code": getattr(outcome, "exit_code", None),
        "outcome.verdict": getattr(outcome, "verdict", None),
        "outcome.stderr_state": getattr(outcome, "stderr_state", None),
    }


# --- Given ----------------------------------------------------------------


@given(
    parsers.parse("a fresh source tree of kind {source_kind}"),
    target_fixture="source_kind",
)
def given_fresh_source_tree_of_kind(state, source_kind) -> SourceTreeKind:
    state["source_kind"] = SourceTreeKind(source_kind)
    state["before_install"] = _install_snapshot(state)
    return state["source_kind"]


@given("the install plugin has completed installation against that source tree")
def given_install_plugin_completed(freshness_probe, state, tmp_path) -> None:
    state["installed"] = freshness_probe.run_install_plugin(
        tmp_path, source_kind=state["source_kind"]
    )


# --- When -----------------------------------------------------------------


@when("the install plugin completes installation against that source tree")
def when_install_plugin_completes(freshness_probe, state, tmp_path) -> None:
    state["installed"] = freshness_probe.run_install_plugin(
        tmp_path, source_kind=state["source_kind"]
    )


@when(parsers.parse("the operator mutates the installed file {mutated_file}"))
def when_operator_mutates_installed_file(freshness_probe, state, mutated_file) -> None:
    state["mutated_rel_path"] = Path(mutated_file)
    freshness_probe.mutate_installed_file(state["installed"], state["mutated_rel_path"])


@when("the operator imports `des.cli` against the installed tree")
def when_operator_imports_des_cli_against_installed_tree(
    freshness_probe, state
) -> None:
    # Mandate-12 SSOT (2026-05-23): populate the SAME `state["before"]` key
    # slice-01's WHEN step uses, so slice-01's `@then PROCEEDS / REFUSES`
    # bodies (now the single SSOT for those Gherkin phrases) read a
    # well-defined snapshot regardless of which slice triggered the WHEN.
    state["before"] = _gate_snapshot(state)
    state["outcome"] = freshness_probe.spawn_gate_against(
        _installed_path_probe_for(state["installed"]),
        opt_out=state.get("opt_out", FreshnessOptOut.UNSET),
    )


# --- Then -----------------------------------------------------------------


@then("the installed package contains a `_install_manifest.json` file")
def then_installed_package_contains_manifest(state) -> None:
    state["manifest_tree_hash_matches_recomputed"] = state.get(
        "manifest_tree_hash_matches_recomputed", None
    )
    _assert_install_observable(state, key="installed.manifest_present", value=True)


@then("the manifest has schema_version 1")
def then_manifest_schema_version_one(state) -> None:
    _assert_install_observable(state, key="installed.manifest.schema_version", value=1)


@then(parsers.parse("the manifest field `source_kind` is {source_kind}"))
def then_manifest_source_kind_is(state, source_kind) -> None:
    _assert_install_observable(
        state,
        key="installed.manifest.source_kind",
        value=SourceTreeKind(source_kind).value,
    )


@then("the manifest field `tree_hash` matches the recomputed tree-hash")
def then_manifest_tree_hash_matches_recomputed(freshness_probe, state) -> None:
    recomputed = freshness_probe.recompute_tree_hash(state["installed"])
    _assert_tree_hash_matches(state, recomputed=recomputed)


# NOTE (Mandate-12 SSOT, 2026-05-23): the `@then` bodies for
#   "the freshness gate PROCEEDS the invocation with exit code 0"
#   "the freshness gate REFUSES the invocation with exit code 78"
# live ONCE in `steps_slice_01_walking_skeleton.py` (SSOT for this domain
# noun). pytest-bdd registers step text globally; redefining them here would
# shadow slice-01's bodies and either KeyError on `state["before"]` or
# silently drift the contract. Slice-02's WHEN step populates the SAME
# `state["before"]` key slice-01 uses, so slice-01's bodies work for both
# slices unchanged.


@then(parsers.parse("the gate reports state {state_letter}"))
def then_gate_reports_state(state, state_letter) -> None:
    expected_state = FreshnessState(state_letter).value
    after = _gate_snapshot(state)
    assert after["outcome.stderr_state"] == expected_state, (
        f"expected gate to report state={expected_state!r} on stderr; "
        f"got state={after['outcome.stderr_state']!r}; "
        f"stderr={getattr(state.get('outcome'), 'stderr_text', None)!r}"
    )


@then("the refusal reason cites the diverged file's tree-hash component")
def then_refusal_reason_cites_diverged_file_hash(state) -> None:
    stderr = getattr(state.get("outcome"), "stderr_text", "") or ""
    relpath = state["mutated_rel_path"].as_posix()
    assert relpath in stderr or "tree_hash" in stderr, (
        f"expected refusal reason on stderr to cite the diverged file "
        f"({relpath!r}) or the tree_hash component; "
        f"got stderr={stderr!r}"
    )


# --- Internal helpers (pure, no business logic) --------------------------


def _installed_path_probe_for(installed):
    """Adapt an `InstalledTree` to the `InstalledPathProbe` shape that
    `FreshnessProbeFixture.spawn_gate_against` consumes.

    Pure function — no I/O, no side effects.
    """
    from steps.domain_types import InstalledPathProbe  # local import; pure shape

    return InstalledPathProbe(
        root=installed.package_root,
        has_manifest=installed.manifest is not None,
        manifest_path=installed.manifest_path,
    )


def _assert_install_observable(state, *, key, value) -> None:
    """Universe-bound install-observable assertion.

    Asserts a single INSTALL_UNIVERSE key transitioned from None (pre-install
    sentinel) to the expected value, with every other universe entry
    unchanged. Mandate 8 fail-closed.
    """
    after = _install_snapshot(state)
    assert_state_delta(
        before={k: state["before_install"][k] for k in (key,)},
        after={k: after[k] for k in (key,)},
        universe=frozenset({key}),
        expected={key: set_to(value)},
    )


def _assert_tree_hash_matches(state, *, recomputed) -> None:
    """Universe-bound assertion that manifest.tree_hash == recomputed hash.

    Captured into the universe via the
    `installed.manifest.tree_hash_matches_recomputed` boolean (computed once
    here, then asserted via set_to(True)). Keeps the universe entry
    port-exposed (a boolean equality observable, not the raw hash string).
    """
    installed = state["installed"]
    matches = (
        installed.manifest is not None and installed.manifest.tree_hash == recomputed
    )
    state["manifest_tree_hash_matches_recomputed"] = matches
    after = _install_snapshot(state)
    assert_state_delta(
        before={
            "installed.manifest.tree_hash_matches_recomputed": state["before_install"][
                "installed.manifest.tree_hash_matches_recomputed"
            ]
        },
        after={
            "installed.manifest.tree_hash_matches_recomputed": after[
                "installed.manifest.tree_hash_matches_recomputed"
            ]
        },
        universe=frozenset({"installed.manifest.tree_hash_matches_recomputed"}),
        expected={
            "installed.manifest.tree_hash_matches_recomputed": set_to(True),
        },
    )
