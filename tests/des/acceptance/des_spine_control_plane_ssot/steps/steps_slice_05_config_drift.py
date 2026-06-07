"""Step bodies for des-spine-control-plane-ssot slice-05 (config-asset drift).

Mandate-12 criterion 3: every step body is ≤2 statements, ends in a single
`config_drift_fixture.<method>(...)` call (or one assertion), and contains zero
control flow (`if`/`for`/`while`/`try`). All business logic lives in
`ConfigDriftFixture` (`composition_slice_05.py`).

Mandate 8: state-mutating assertions go through `assert_state_delta(before,
after, universe, expected)` from `tests.common.state_delta`. Universe entries are
port-exposed observables on `ConfigHookOutcome` (exit_code, verdict) — never
Popen handles, never env dicts, never internal manifest fields.

Mandate 9 v2: layer 3/4 (subprocess against tmp_path, @real-io — the driven set
includes a real filesystem adapter) → example-only. PBT machinery is
intentionally NOT imported.

Mandate 11: AT-02 (fresh-config silent) is one explicit named example. No PBT.

Mandate-13: ATs drive through the production HOOK ENTRYPOINT (subprocess
`python -c "import ...claude_code_hook_adapter"`) — NEVER a direct
`from des.runtime.freshness import ...` invocation in test bodies.
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from tests.common.state_delta import assert_state_delta, set_to

from .domain_types_slice_05 import (
    ADJACENCY_BY_PHRASE_05,
    CONFIG_DRIFT_BY_PHRASE,
    HEALTH_GATE_INSTALL_FRESHNESS_CONFIG_DRIFT,
    FreshnessOptOut,
    HookVerdict,
    StructuredConfigEventName,
)


# --- Universe (Mandate 8): port-exposed observables only -----------------

VERDICT_UNIVERSE = frozenset(
    {
        "outcome.exit_code",
        "outcome.verdict",
    }
)


def _verdict_snapshot(state: dict) -> dict:
    """Build a universe snapshot of the verdict observables. Pure function."""
    outcome = state.get("outcome")
    return {
        "outcome.exit_code": getattr(outcome, "exit_code", None),
        "outcome.verdict": getattr(outcome, "verdict", None),
    }


# --- Given ----------------------------------------------------------------


@given(parsers.parse("a synthetic installed spine whose {drift_phrase}"))
def given_installed_spine_config_drift(
    config_drift_fixture, state, drift_phrase: str
) -> None:
    state["installed"] = config_drift_fixture.build_installed_spine(
        config_drift=CONFIG_DRIFT_BY_PHRASE[drift_phrase]
    )


@given(parsers.parse("the operator runs from a {adjacency_phrase}"))
def given_operator_checkout(config_drift_fixture, state, adjacency_phrase: str) -> None:
    state["checkout"] = config_drift_fixture.build_checkout(
        adjacency=ADJACENCY_BY_PHRASE_05[adjacency_phrase]
    )


@given("the operator has set the freshness opt-out")
def given_operator_opt_out(state) -> None:
    state["opt_out"] = FreshnessOptOut.SKIP


# --- When -----------------------------------------------------------------


@when("a spine hook fires on the hook hot path")
def when_spine_hook_fires(config_drift_fixture, state) -> None:
    state["before"] = _verdict_snapshot(state)
    state["outcome"] = config_drift_fixture.fire_hook(
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
    "the operator sees a LOUD `install-freshness.config-drift` warning naming the stale asset"
)
def then_operator_sees_loud_config_drift_warning(state) -> None:
    outcome = state["outcome"]
    assert outcome.stderr_event == StructuredConfigEventName.CONFIG_DRIFT.value, (
        f"SYS-4 / AD-27 config-asset envelope assertion: expected the LOUD "
        f"config-drift event {StructuredConfigEventName.CONFIG_DRIFT.value!r} on "
        f"stderr (the freshness envelope must hash the shipped `lib/nWave/` config "
        f"assets, not only `*.py`); got event={outcome.stderr_event!r}; "
        f"stderr={outcome.stderr_text!r}"
    )
    assert outcome.stderr_remediation, (
        "config-drift warning must name a remediation (DISCUSS D3 / KPI-2: "
        f"business-name + remediation); remediation={outcome.stderr_remediation!r}"
    )


@then("the operator sees no freshness warning of any kind")
def then_operator_sees_no_warning(state) -> None:
    outcome = state["outcome"]
    assert outcome.stderr_event is None, (
        f"fresh-config invariant: the hook must proceed SILENTLY when the shipped "
        f"config matches the install snapshot (no freshness event on stderr); got "
        f"event={outcome.stderr_event!r}; stderr={outcome.stderr_text!r}"
    )


@then(
    "the persistent audit log records one config-drift freshness event naming the remediation"
)
def then_audit_log_records_config_drift_event(config_drift_fixture, state) -> None:
    drift = config_drift_fixture.config_drift_audit_records(state["outcome"])
    assert len(drift) == 1 and config_drift_fixture.record_has_remediation(drift), (
        f"DV-5 dual-emit / KPI-1 sink: expected exactly one persisted "
        f"{HEALTH_GATE_INSTALL_FRESHNESS_CONFIG_DRIFT} record (with a remediation, "
        f"KPI-2) in the JsonlAuditLogWriter SSOT (`audit-*.log`); got {len(drift)} "
        f"config-drift of {len(state['outcome'].audit_records)} total: "
        f"{state['outcome'].audit_records!r}"
    )
