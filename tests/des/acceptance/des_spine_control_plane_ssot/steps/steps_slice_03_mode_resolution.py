"""Step bodies for des-spine-control-plane-ssot slice-03 (mode-resolution SSOT).

Mandate-12 criterion 3: every step body is <=2 statements, ends in a single
`mode_resolution_fixture.<method>(...)` call (or one `assert_state_delta` /
assertion), and contains zero control flow (`if`/`for`/`while`/`try`). All
business logic lives in `ModeResolutionFixture` (composition_slice_03.py).

Mandate 8: state-mutating assertions go through `assert_state_delta(before,
after, universe, expected)` from `tests.common.state_delta`. Universe entries are
port-exposed observables on `VerifyRun` (exit_code, outcome, roadmap_hunt) —
never Popen handles, never env dicts, never raw stream bytes.

Mandate 9 v2: layer 3 (subprocess against tmp_path, @real-io — the driven set
includes a real filesystem adapter the spine CLIs read config + ledger from) ->
example-only. PBT machinery is intentionally NOT imported.

Mandate 11: the #65 phantom-roadmap path (AT-01) is one explicit named example.

Mandate-13: ATs drive through the production `des verify-integrity` + `des
init-log` CLIs (subprocess) — NEVER a direct
`from des.application.workflow_mode import _resolve_workflow_mode` or
`from des.cli.init_log import resolve_dispatch_mode` invocation in test bodies.
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from tests.common.state_delta import assert_state_delta, set_to

from .domain_types_slice_03 import (
    MODE_CONFIG_BY_PHRASE,
    DispatchOutcome,
    VerifyOutcome,
)


# --- Universe (Mandate 8): port-exposed observables only -----------------

VERIFY_UNIVERSE = frozenset(
    {
        "verify.exit_code",
        "verify.outcome",
        "verify.roadmap_hunt",
    }
)


def _verify_snapshot(state: dict) -> dict:
    """Build a universe snapshot of the verify observables. Pure function.

    Returns None sentinels for unobserved keys so the before-snapshot is
    well-defined before the verifier is fired.
    """
    run = state.get("verify_run")
    return {
        "verify.exit_code": getattr(run, "exit_code", None),
        "verify.outcome": getattr(run, "outcome", None),
        "verify.roadmap_hunt": getattr(run, "roadmap_hunt", None),
    }


# --- Given ----------------------------------------------------------------


@given(parsers.parse("a {mode_phrase}"))
def given_project(mode_resolution_fixture, state, mode_phrase: str) -> None:
    state["project"] = mode_resolution_fixture.build_project(
        mode_config=MODE_CONFIG_BY_PHRASE[mode_phrase]
    )


# --- When -----------------------------------------------------------------


@when("the operator runs verify-integrity on the project")
def when_operator_runs_verify(mode_resolution_fixture, state) -> None:
    state["before"] = _verify_snapshot(state)
    state["verify_run"] = mode_resolution_fixture.run_verify_integrity(state["project"])


@when("the operator starts a DELIVER dispatch and runs verify-integrity on the project")
def when_operator_runs_both_ports(mode_resolution_fixture, state) -> None:
    state["dispatch_run"] = mode_resolution_fixture.run_init_log(state["project"])
    state["verify_run"] = mode_resolution_fixture.run_verify_integrity(state["project"])


# --- Then -----------------------------------------------------------------


@then(
    "verify-integrity resolves the active mode and checks the artifacts it "
    "actually wrote"
)
def then_verify_resolves_active_mode(state) -> None:
    after = _verify_snapshot(state)
    assert_state_delta(
        before={k: state["before"][k] for k in VERIFY_UNIVERSE},
        after={k: after[k] for k in VERIFY_UNIVERSE},
        universe=VERIFY_UNIVERSE,
        expected={
            "verify.outcome": set_to(VerifyOutcome.RESOLVED_ATDD_PURE),
            "verify.roadmap_hunt": set_to(False),
            "verify.exit_code": _is_resolved_exit,
        },
    )


@then("verify-integrity never hunts for a roadmap the active mode never wrote")
def then_verify_no_phantom_roadmap(state) -> None:
    run = state["verify_run"]
    assert not run.roadmap_hunt, (
        "#65-dissolution (DDD-5/7): on an unconfigured atdd_pure project the "
        "verifier must NOT mis-resolve to classic and refuse exit 2 "
        "'roadmap.json not found' — the atdd_pure spine is roadmap-free, so a "
        f"missing roadmap is a non-event; got exit {run.exit_code}, "
        f"stdout={run.stdout!r} stderr={run.stderr!r}"
    )


@then("the DELIVER dispatch and verify-integrity agree on one mode answer")
def then_ports_agree(mode_resolution_fixture, state) -> None:
    assert mode_resolution_fixture.ports_agree_on_atdd_pure(
        state["verify_run"], state["dispatch_run"]
    ), (
        "default-consistency (Context-B referential transparency / KPI-3): on "
        "the SAME unconfigured project, the DELIVER-dispatch port and the verify "
        "port must resolve the SAME mode answer (atdd_pure, DDD-7). Today they "
        "DIVERGE — init-log creates a classic log while verify hunts for a "
        f"phantom roadmap. dispatch={state['dispatch_run'].outcome!r} "
        f"verify={state['verify_run'].outcome!r}"
    )


@then("the DELIVER dispatch refuses to create a roadmap-based log under that mode")
def then_dispatch_refuses_atdd_pure(state) -> None:
    run = state["dispatch_run"]
    assert run.outcome is DispatchOutcome.REFUSED_ATDD_PURE, (
        "the DELIVER port resolving atdd_pure is OBSERVABLE as init-log refusing "
        "to create a roadmap-based execution-log (the atdd_pure spine is "
        "roadmap-free / execution-log-free, ADR-028 D4.1); today it CREATES a "
        f"classic log on an unconfigured project. got outcome={run.outcome!r} "
        f"exit={run.exit_code} stdout={run.stdout!r} stderr={run.stderr!r}"
    )


# --- universe predicate (Mandate 8): atdd_pure-branch exit, value-agnostic ---


def _is_resolved_exit(old, new) -> bool:
    """state-delta predicate `(old, new) -> bool`: an atdd_pure-branch exit code.

    Once the verifier resolves atdd_pure it reaches a verdict by reading the
    AT-completion ledger: exit 0 (clean ledger + feature-end cycle) or exit 1
    (an atdd_pure-shaped integrity violation). Either is the resolved state; the
    forbidden value is exit 2 (the classic `roadmap.json not found` phantom). The
    universe predicate pins membership in {0, 1}, keeping it value-agnostic — the
    exact code depends on the synthetic ledger's contents.
    """
    return new in (0, 1)


_is_resolved_exit.__name__ = "is_resolved_atdd_pure_exit"
