"""Step bodies for des-spine-control-plane-ssot slice-01 (hook-freshness wiring).

Mandate-12 criterion 3: every step body is ≤2 statements, ends in a single
`hook_freshness_fixture.<method>(...)` call (or one assertion), and contains zero
control flow (`if`/`for`/`while`/`try`). All business logic lives in
`HookFreshnessFixture` (conftest.py).

Mandate 8: state-mutating assertions go through `assert_state_delta(before, after,
universe, expected)` from `tests.common.state_delta`. Universe entries are
port-exposed observables on `HookInvocationOutcome` (exit_code, verdict,
stderr_event) — never Popen handles, never env dicts, never internal fields.

Mandate 9 v2: layer 3/4 (subprocess against tmp_path, @real-io — the driven set
includes a real filesystem adapter) → example-only. PBT machinery is intentionally
NOT imported.

Mandate 11: AT-02 (customer-silent) is one explicit named example. No PBT.

Mandate-13: ATs drive through the production HOOK ENTRYPOINT (subprocess
`python -m ...claude_code_hook_adapter pre-tool-use`) — NEVER a direct
`from des.runtime.freshness import ...` invocation in test bodies.
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from tests.common.state_delta import assert_state_delta, set_to

from .domain_types import (
    ADJACENCY_BY_PHRASE,
    DRIFT_BY_PHRASE,
    HEALTH_GATE_INSTALL_FRESHNESS_STALE,
    FreshnessOptOut,
    HookVerdict,
    StructuredEventName,
)


# --- Universe (Mandate 8): port-exposed observables only -----------------

VERDICT_UNIVERSE = frozenset(
    {
        "outcome.exit_code",
        "outcome.verdict",
    }
)


def _verdict_snapshot(state: dict) -> dict:
    """Build a universe snapshot of the verdict observables. Pure function.

    Returns None sentinels for unobserved keys so the before-snapshot is
    well-defined before the hook is fired.
    """
    outcome = state.get("outcome")
    return {
        "outcome.exit_code": getattr(outcome, "exit_code", None),
        "outcome.verdict": getattr(outcome, "verdict", None),
    }


# --- Given ----------------------------------------------------------------


@given(parsers.parse("a synthetic installed spine whose {drift_phrase}"))
def given_installed_spine_drift(
    hook_freshness_fixture, state, drift_phrase: str
) -> None:
    state["installed"] = hook_freshness_fixture.build_installed_spine(
        drift=DRIFT_BY_PHRASE[drift_phrase]
    )


@given(parsers.parse("a synthetic installed spine on a {drift_phrase}"))
def given_installed_spine_customer(
    hook_freshness_fixture, state, drift_phrase: str
) -> None:
    state["installed"] = hook_freshness_fixture.build_installed_spine(
        drift=DRIFT_BY_PHRASE[drift_phrase]
    )


@given(parsers.parse("the operator runs from a {adjacency_phrase}"))
def given_operator_checkout(
    hook_freshness_fixture, state, adjacency_phrase: str
) -> None:
    state["checkout"] = hook_freshness_fixture.build_checkout(
        adjacency=ADJACENCY_BY_PHRASE[adjacency_phrase]
    )


@given("the operator has set the freshness opt-out")
def given_operator_opt_out(state) -> None:
    state["opt_out"] = FreshnessOptOut.SKIP


# --- When -----------------------------------------------------------------


@when("a spine hook fires on the hook hot path")
def when_spine_hook_fires(hook_freshness_fixture, state) -> None:
    state["before"] = _verdict_snapshot(state)
    state["outcome"] = hook_freshness_fixture.fire_hook(
        state["installed"],
        state["checkout"],
        opt_out=state.get("opt_out", FreshnessOptOut.UNSET),
    )


# --- Then -----------------------------------------------------------------


@then("the spine hook proceeds the session with exit code 0")
def then_hook_proceeds_exit_0(state) -> None:
    after = _verdict_snapshot(state)
    assert_state_delta(
        before={k: state["before"][k] for k in VERDICT_UNIVERSE},
        after={k: after[k] for k in VERDICT_UNIVERSE},
        universe=VERDICT_UNIVERSE,
        expected={
            "outcome.exit_code": set_to(0),
            "outcome.verdict": set_to(HookVerdict.PROCEED),
        },
    )


@then(
    "the operator sees a LOUD `install-freshness.stale` warning naming the digest mismatch"
)
def then_operator_sees_loud_stale_warning(state) -> None:
    outcome = state["outcome"]
    assert outcome.stderr_event == StructuredEventName.STALE.value, (
        f"DV-2 reaches-the-probe assertion: expected the LOUD stale event "
        f"{StructuredEventName.STALE.value!r} on stderr (the gate must REACH the "
        f"probe despite the project `.git/`, not autoskip); got "
        f"event={outcome.stderr_event!r}; stderr={outcome.stderr_text!r}"
    )
    assert outcome.stderr_remediation, (
        "stale warning must name a remediation (DISCUSS D3 / KPI-2: business-name "
        f"+ remediation, never a bare event); remediation={outcome.stderr_remediation!r}"
    )


@then("the operator sees no freshness warning of any kind")
def then_operator_sees_no_warning(state) -> None:
    outcome = state["outcome"]
    assert outcome.stderr_event is None, (
        f"install-fidelity / fresh-install invariant: the hook must proceed SILENTLY "
        f"(no freshness event on stderr); got event={outcome.stderr_event!r}; "
        f"stderr={outcome.stderr_text!r}"
    )


@then(parsers.parse("the operator sees a structured `{event_name}` acknowledgement"))
def then_operator_sees_event(state, event_name: str) -> None:
    assert state["outcome"].stderr_event == event_name, (
        f"expected structured event {event_name!r} on stderr; got "
        f"event={state['outcome'].stderr_event!r}; stderr={state['outcome'].stderr_text!r}"
    )


@then(parsers.parse("the operator sees no `{forbidden_event}` warning"))
def then_operator_sees_no_forbidden_event(state, forbidden_event: str) -> None:
    assert state["outcome"].stderr_event != forbidden_event, (
        f"opt-out precedence violated: gate emitted forbidden event "
        f"{forbidden_event!r} despite NWAVE_FRESHNESS=skip; "
        f"stderr={state['outcome'].stderr_text!r}"
    )


@then(
    "the persistent audit log records one stale-install freshness event naming the remediation"
)
def then_audit_log_records_stale_event(hook_freshness_fixture, state) -> None:
    stale = hook_freshness_fixture.stale_audit_records(state["outcome"])
    assert len(stale) == 1 and hook_freshness_fixture.record_has_remediation(stale), (
        f"DV-5 dual-emit / KPI-1 sink: expected exactly one persisted "
        f"{HEALTH_GATE_INSTALL_FRESHNESS_STALE} record (with a remediation, KPI-2) "
        f"in the JsonlAuditLogWriter SSOT (`audit-*.log`, read by JsonlAuditLogReader "
        f"+ the KPI-1 query path); got {len(stale)} stale of "
        f"{len(state['outcome'].audit_records)} total: {state['outcome'].audit_records!r}"
    )
