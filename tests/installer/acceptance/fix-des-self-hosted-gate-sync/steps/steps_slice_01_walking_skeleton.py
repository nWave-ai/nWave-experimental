"""Step bodies for slice-01 walking-skeleton ATs.

Layer: 3 (subprocess against tmp_path-installed `des/` tree) — per Mandate 9
this layer is example-only; per Mandate 11 sad paths are explicit named
examples. PBT machinery is intentionally NOT imported.

Mandate-12: every step body is ≤2 statements, ends in
`freshness_probe.<method>(...)`, contains no control flow. Business logic
lives in `FreshnessProbeFixture` (conftest.py) which in DELIVER will delegate
to the production `des.runtime.freshness` composition root.

Mandate 8: assertions go through `assert_state_delta(before, after, universe,
expected)` from `tests.common.state_delta`. Universe entries are port-exposed
observables on `GateInvocationOutcome` — never Popen handles, never internal
fields. The before-state captures the universe BEFORE the gate runs (no
outcome observed yet); the after-state captures it AFTER.
"""

from __future__ import annotations

import importlib.util as _importlib_util
import sys
from pathlib import Path


# Match the kebab-case workaround in the sibling conftest.py — inject the
# feature root so `from steps.domain_types import ...` resolves against
# THIS feature's local modules.
_FEATURE_ROOT = Path(__file__).resolve().parent.parent
if str(_FEATURE_ROOT) not in sys.path:
    sys.path.insert(0, str(_FEATURE_ROOT))

from pytest_bdd import given, then, when  # noqa: E402
from steps.domain_types import (  # noqa: E402
    FreshnessOptOut,
    GateVerdict,
    SourceTreeKind,
)


# Load THIS feature's conftest by absolute path under a unique module name
# instead of `from conftest import ...`. Bare `from conftest import ...` is
# globally ambiguous across the test tree: every feature directory injects
# its own `_FEATURE_ROOT` onto `sys.path[0]`, but `sys.modules['conftest']`
# is single-binding — whichever feature is collected first wins, so a
# pre-commit run scoped to multiple features (e.g. `tests/des/...` +
# `tests/installer/.../fix-des-self-hosted-gate-sync/`) sees
# `parse_structured_event_line` resolve against the WRONG conftest. The
# importlib-by-file-path pattern below mirrors what this feature's own
# `conftest.py` already does to load the steps modules with unique names.
_FIX_DES_GATE_SYNC_CONFTEST_MOD_NAME = (
    "fix_des_self_hosted_gate_sync_local_conftest_for_slice_01_steps"
)
_conftest_path = _FEATURE_ROOT / "conftest.py"
if _FIX_DES_GATE_SYNC_CONFTEST_MOD_NAME not in sys.modules:
    _spec = _importlib_util.spec_from_file_location(
        _FIX_DES_GATE_SYNC_CONFTEST_MOD_NAME,
        str(_conftest_path),
    )
    _mod = _importlib_util.module_from_spec(_spec)
    sys.modules[_FIX_DES_GATE_SYNC_CONFTEST_MOD_NAME] = _mod
    _spec.loader.exec_module(_mod)
parse_structured_event_line = sys.modules[
    _FIX_DES_GATE_SYNC_CONFTEST_MOD_NAME
].parse_structured_event_line

from tests.common.state_delta import (  # noqa: E402
    assert_state_delta,
    set_to,
)


# `scenarios()` is intentionally NOT called here — the `@scenario` shells
# live in the sibling `test_slice_01_walking_skeleton.py` at the feature
# root, matching the backup-retention-policy precedent for kebab-case
# acceptance feature directories under tests/installer/acceptance/.


# --- Universe (Mandate 8): port-exposed observables only -----------------

GATE_UNIVERSE = frozenset(
    {
        "outcome.exit_code",
        "outcome.verdict",
        "outcome.stderr_event",
        "outcome.stderr_state",
    }
)


def _snapshot(state: dict) -> dict:
    """Build a dict snapshot of the universe from the scenario state.

    Pure function. Returns sentinels (None) for unobserved keys so the
    before-snapshot is well-defined before any outcome is captured.
    """
    outcome = state.get("outcome")
    return {
        "outcome.exit_code": getattr(outcome, "exit_code", None),
        "outcome.verdict": getattr(outcome, "verdict", None),
        "outcome.stderr_event": getattr(outcome, "stderr_event", None),
        "outcome.stderr_state": getattr(outcome, "stderr_state", None),
    }


# --- Given ----------------------------------------------------------------


@given("a synthetic installed DES tree at the standard install path")
def given_installed_tree_exists(freshness_probe, state, tmp_path) -> None:
    state["installed_tmp_root"] = tmp_path


@given("the installed tree has no `_install_manifest.json`")
def given_installed_tree_no_manifest(freshness_probe, state) -> None:
    state["installed"] = freshness_probe.build_installed_tree(
        state["installed_tmp_root"], with_manifest=False
    )


@given("the installed tree carries a manifest whose `source_tree` is not reachable")
def given_installed_tree_manifest_source_unreachable(freshness_probe, state) -> None:
    state["installed"] = freshness_probe.build_installed_tree(
        state["installed_tmp_root"],
        with_manifest=True,
        manifest_content={
            "schema_version": 1,
            "installed_version": "3.15.1",
            "installed_at_iso": "2026-05-23T02:14:33Z",
            "source_tree": "/nonexistent/customer/host/has/no/repo",
            "source_commit": "",
            "source_dirty": False,
            "source_kind": SourceTreeKind.WHEEL.value,
            "tree_hash": "sha256:placeholder",
        },
    )


@given("the operator sets the freshness opt-out to skip")
def given_operator_sets_freshness_opt_out_to_skip(state) -> None:
    state["opt_out"] = FreshnessOptOut.SKIP


# --- When -----------------------------------------------------------------


@when("the operator imports `des.cli` against that installed tree")
def when_operator_imports_des_cli(freshness_probe, state) -> None:
    state["before"] = _snapshot(state)
    state["outcome"] = freshness_probe.spawn_gate_against(
        state["installed"], opt_out=state.get("opt_out", FreshnessOptOut.UNSET)
    )


# --- Then -----------------------------------------------------------------


# SSOT-narrowed verdict universe (Mandate-12 + Mandate 8, 2026-05-23):
#
# Both PROCEED and REFUSE scenarios across slice-01 (DEGRADED) and slice-02
# (state D mutation) share ONLY the `(exit_code, verdict)` invariant on the
# top-level Gherkin step. The stderr surface (`stderr_event`, `stderr_state`)
# diverges per scenario:
#   slice-01 DEGRADED REFUSE → trailing And-steps assert refused+DEGRADED
#   slice-02 state-D REFUSE  → trailing And-steps assert state D + relpath
#   slice-01 silent  PROCEED → trailing And-step asserts no stderr event
#   slice-01 skip    PROCEED → trailing And-steps assert skipped + no refusal
#   slice-02 fresh   PROCEED → trailing And-step asserts state C
#
# Narrowing the body universe to {exit_code, verdict} keeps slice-01's body
# as the SSOT for both PROCEED and REFUSE step text, regardless of slice.
VERDICT_UNIVERSE = frozenset(
    {
        "outcome.exit_code",
        "outcome.verdict",
    }
)


@then("the freshness gate REFUSES the invocation with exit code 78")
def then_gate_refuses_exit_78(state) -> None:
    after = _snapshot(state)
    assert_state_delta(
        before={k: state["before"][k] for k in VERDICT_UNIVERSE},
        after={k: after[k] for k in VERDICT_UNIVERSE},
        universe=VERDICT_UNIVERSE,
        expected={
            "outcome.exit_code": set_to(78),
            "outcome.verdict": set_to(GateVerdict.REFUSE),
        },
    )


@then("the gate emits a structured event `des.runtime.freshness.refused`")
def then_gate_emits_refused_event(state) -> None:
    event, _ = parse_structured_event_line(state["outcome"].stderr_text)
    assert event == "des.runtime.freshness.refused", (
        f"expected structured event 'des.runtime.freshness.refused' on stderr; "
        f"got event={event!r}; stderr={state['outcome'].stderr_text!r}"
    )


# NOTE (Mandate-12 SSOT, 2026-05-23): the `@then("the gate reports state
# DEGRADED")` decorator that previously lived here has been removed. The
# parametrized `@then(parsers.parse("the gate reports state {state_letter}"))`
# in `steps_slice_02_install_manifest.py` is the SSOT for that step phrase
# across BOTH slices — it handles DEGRADED (slice-01), C and D (slice-02)
# uniformly via the FreshnessState enum.


@then("the freshness gate PROCEEDS the invocation with exit code 0")
def then_gate_proceeds_exit_0(state) -> None:
    after = _snapshot(state)
    assert_state_delta(
        before={k: state["before"][k] for k in VERDICT_UNIVERSE},
        after={k: after[k] for k in VERDICT_UNIVERSE},
        universe=VERDICT_UNIVERSE,
        expected={
            "outcome.exit_code": set_to(0),
            "outcome.verdict": set_to(GateVerdict.PROCEED),
        },
    )


@then("no structured event is emitted on standard error")
def then_no_structured_event_on_stderr(state) -> None:
    event, _ = parse_structured_event_line(state["outcome"].stderr_text)
    assert event is None, (
        f"customer state A must be silent (no structured freshness event); "
        f"got event={event!r}; stderr={state['outcome'].stderr_text!r}"
    )


@then("the gate emits a structured event `des.runtime.freshness.skipped`")
def then_gate_emits_skipped_event(state) -> None:
    event, _ = parse_structured_event_line(state["outcome"].stderr_text)
    assert event == "des.runtime.freshness.skipped", (
        f"expected structured event 'des.runtime.freshness.skipped' on stderr "
        f"(NWAVE_FRESHNESS=skip is the audit-bearing bypass per §1.8); "
        f"got event={event!r}; stderr={state['outcome'].stderr_text!r}"
    )


@then("no refusal is reported on standard error")
def then_no_refusal_on_stderr(state) -> None:
    event, _ = parse_structured_event_line(state["outcome"].stderr_text)
    assert event != "des.runtime.freshness.refused", (
        f"opt-out=skip must NEVER coexist with a refused event; "
        f"got event={event!r}; stderr={state['outcome'].stderr_text!r}"
    )
