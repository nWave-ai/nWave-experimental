"""Step bodies for the fix-freshness-gate-dev-checkout-autoskip walking skeleton.

Mandate-12 criterion 3: every step body is ≤2 statements, ends in a single
`autoskip_fixture.<method>(...)` call, and contains zero control flow
(`if`/`for`/`while`/`try`). All business logic lives in
`FreshnessAutoskipFixture` (conftest.py).

Mandate 8: assertions go through `assert_state_delta(before, after, universe,
expected)` from `tests.common.state_delta`. Universe entries are port-exposed
observables on `GateInvocationOutcome` (exit_code, verdict, stderr_event) —
never Popen handles, never env dicts, never internal fields.

Mandate 9: layer 3 (subprocess against tmp_path) → example-only. PBT
machinery is intentionally NOT imported.

Mandate 11: AT-02 sad path is one explicit named example. No PBT generation.

Mandate-13: ATs drive through the production composition root (subprocess
`import des.cli`) — NEVER direct `from des.runtime.freshness import ...`
invocation in test bodies.
"""

from __future__ import annotations

import sys
from pathlib import Path


# Match the snake_case workaround pattern used by the sibling conftest —
# inject the feature root so `from freshness_steps.domain_types import ...`
# resolves against THIS feature's local module. The subpackage is named
# `freshness_steps` (not `steps`) to keep this feature's namespace distinct
# from the sibling installer feature's `steps/` package.
_FEATURE_ROOT = Path(__file__).resolve().parent.parent
if str(_FEATURE_ROOT) not in sys.path:
    sys.path.insert(0, str(_FEATURE_ROOT))

from freshness_steps.domain_types import (
    ADJACENCY_BY_PHRASE,
    GateVerdict,
    StructuredEventName,
)
from pytest_bdd import given, parsers, then, when

from tests.common.state_delta import (
    assert_state_delta,
    set_to,
)


# --- Universe (Mandate 8): port-exposed observables only -----------------

GATE_UNIVERSE = frozenset(
    {
        "outcome.exit_code",
        "outcome.verdict",
        "outcome.stderr_event",
    }
)

VERDICT_UNIVERSE = frozenset(
    {
        "outcome.exit_code",
        "outcome.verdict",
    }
)


def _snapshot(state: dict) -> dict:
    """Build a dict snapshot of the universe from the scenario state.

    Pure function. Returns None sentinels for unobserved keys so the
    before-snapshot is well-defined before any outcome is captured.
    """
    outcome = state.get("outcome")
    return {
        "outcome.exit_code": getattr(outcome, "exit_code", None),
        "outcome.verdict": getattr(outcome, "verdict", None),
        "outcome.stderr_event": getattr(outcome, "stderr_event", None),
    }


# --- Given ----------------------------------------------------------------


@given("a synthetic installed DES tree at the standard install path")
def given_installed_tree_exists(autoskip_fixture, state, tmp_path) -> None:
    state["installed_tmp_root"] = tmp_path


@given("the installed tree has no `_install_manifest.json`")
def given_installed_tree_no_manifest(autoskip_fixture, state) -> None:
    state["installed"] = autoskip_fixture.build_installed_tree(
        state["installed_tmp_root"], with_manifest=False
    )


@given(parsers.parse("the operator runs from a {adjacency_phrase}"))
def given_operator_cwd_adjacency(
    autoskip_fixture, state, tmp_path, adjacency_phrase: str
) -> None:
    state["checkout"] = autoskip_fixture.build_checkout_probe(
        tmp_path, adjacency=ADJACENCY_BY_PHRASE[adjacency_phrase]
    )


@given("the operator requests verbose freshness diagnostics")
def given_verbose_freshness_diagnostics(state) -> None:
    state["freshness_mode"] = "verbose"


# --- When -----------------------------------------------------------------


@when("the operator imports `des.cli` against that installed tree")
def when_operator_imports_des_cli(autoskip_fixture, state) -> None:
    state["before"] = _snapshot(state)
    state["outcome"] = autoskip_fixture.spawn_gate_against(
        state["installed"],
        state["checkout"],
        freshness_mode=state.get("freshness_mode"),
    )


# --- Then -----------------------------------------------------------------


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


@then(parsers.parse("the gate emits a structured event `{expected_event}`"))
def then_gate_emits_event(state, expected_event: str) -> None:
    assert state["outcome"].stderr_event == expected_event, (
        f"expected structured event {expected_event!r} on stderr; "
        f"got event={state['outcome'].stderr_event!r}; "
        f"stderr={state['outcome'].stderr_text!r}"
    )


@then(parsers.parse("the gate does not emit a structured event `{forbidden_event}`"))
def then_gate_does_not_emit_event(state, forbidden_event: str) -> None:
    assert state["outcome"].stderr_event != forbidden_event, (
        f"audit-trail invariant violated: gate emitted forbidden event "
        f"{forbidden_event!r} (must be distinguishable from this name); "
        f"stderr={state['outcome'].stderr_text!r}"
    )


@then("the gate emits no freshness diagnostic")
def then_gate_emits_no_freshness_diagnostic(state) -> None:
    assert state["outcome"].stderr_text == ""


# Closed-enum sanity: cite every StructuredEventName the assertions can
# reference so an enum rename surfaces here as an unused-name lint at
# refactor time. Pure import-time side effect — no test runtime cost.
_ENUM_CITATIONS = (
    StructuredEventName.REFUSED,
    StructuredEventName.SKIPPED,
    StructuredEventName.AUTOSKIPPED,
    StructuredEventName.PROCEED,
)
