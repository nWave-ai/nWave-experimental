"""Step bodies for oss-spine-watchdog slice-03 (stale-agent timeout, #68 P2-E).

Mandate-12 criterion 3: every step body is ≤2 statements, ends in a single
`stale_agent_fixture.<method>(...)` call (or one assertion), and contains zero
control flow (`if`/`for`/`while`/`try`). All business logic lives in
`StaleAgentFixture` (composition_slice_03.py).

Mandate 8: the state-mutating outcome assertion goes through
`assert_state_delta(before, after, universe, expected)` from
`tests.common.state_delta`. Universe entries are port-exposed observables on
`StaleCheckOutcome` (`outcome.closed`, `outcome.names_staleness`) — never Popen
handles, never the transcript JSONL bytes, never the raw ledger path (Mandate 8 —
port-exposed observables only).

Mandate 9 v2: layer 3/4 (real git repo + real ledger JSONL + real hook subprocess
against tmp_path, @real-io — the driven set includes a real filesystem adapter +
a real git subprocess + a real hook subprocess) → example-only. PBT machinery is
intentionally NOT imported (Mandate 11 — sad paths enumerated explicitly).

Mandate-13: ATs drive through the production SubagentStop driving port (the real
`handle_subagent_stop` hook subprocess) — NEVER a direct
`from des...subagent_stop_handler import _handle_atdd_pure_return` invocation in
test bodies. The composition fires the hook over its JSON stdin protocol.
"""

from __future__ import annotations

from pytest_bdd import given, then, when

from tests.common.state_delta import assert_state_delta, set_to

from .domain_types_slice_03 import ProgressAge, TerminalPresence


# --- Universe (Mandate 8): port-exposed observables only -----------------

STALE_UNIVERSE = frozenset(
    {
        "outcome.closed",
        "outcome.names_staleness",
    }
)


def _stale_snapshot(state: dict) -> dict:
    """Build a universe snapshot of the stale-check observables. Pure function.

    Returns None sentinels for unobserved keys so the before-snapshot is
    well-defined before the hook fires.
    """
    outcome = state.get("outcome")
    return {
        "outcome.closed": getattr(outcome, "closed", None),
        "outcome.names_staleness": getattr(outcome, "names_staleness", None),
    }


# --- Given ----------------------------------------------------------------


@given("a returning agent whose last progress is older than the stale threshold")
def given_stale_agent_no_terminal(stale_agent_fixture, state_03) -> None:
    state_03["age"] = ProgressAge.STALE
    state_03["terminal"] = TerminalPresence.ABSENT


@given("a returning agent whose last progress is recent")
def given_fresh_agent(stale_agent_fixture, state_03) -> None:
    state_03["age"] = ProgressAge.FRESH
    state_03["terminal"] = TerminalPresence.ABSENT


@given(
    "a returning agent whose last progress is older than the stale threshold "
    "but has already reached a terminal state"
)
def given_stale_agent_already_terminal(stale_agent_fixture, state_03) -> None:
    state_03["age"] = ProgressAge.STALE
    state_03["terminal"] = TerminalPresence.PRESENT


# --- When -----------------------------------------------------------------


@when("the spine evaluates the returning agent when the hook fires")
def when_spine_evaluates_returning_agent(stale_agent_fixture, state_03) -> None:
    stale_agent_fixture.build_returning_agent_repo()
    state_03["before"] = _stale_snapshot(state_03)


@when("the spine finishes evaluating the returning agent")
def when_spine_finishes_evaluating(stale_agent_fixture, state_03) -> None:
    state_03["outcome"] = stale_agent_fixture.run_stale_check(
        age=state_03["age"], terminal=state_03["terminal"]
    )


# --- Then -----------------------------------------------------------------


@then("the spine closes the agent loud instead of leaving it to hang")
def then_spine_closes_loud(state_03) -> None:
    after = _stale_snapshot(state_03)
    assert_state_delta(
        before={k: state_03["before"][k] for k in STALE_UNIVERSE},
        after={k: after[k] for k in STALE_UNIVERSE},
        universe=STALE_UNIVERSE,
        expected={
            "outcome.closed": set_to(True),
            "outcome.names_staleness": set_to(True),
        },
    )


@then("the spine leaves the agent alone because its progress is fresh")
def then_spine_leaves_fresh_alone(state_03) -> None:
    assert state_03["outcome"].closed is False, (
        "fresh-progress guardrail (DESIGN OQ-4 / G-3): the stale terminal must fire "
        "ONLY when the gap between the agent's last progress and now EXCEEDS the "
        "threshold; a RECENT last-progress timestamp (within the threshold) means "
        "the agent is legitimately working, so the spine must leave it alone (no "
        "StaleAgentClosed record, normal return) rather than close it. A check that "
        "closes a returning agent regardless of the gap would wrongly close here. "
        f"Got closed={state_03['outcome'].closed}, "
        f"names_staleness={state_03['outcome'].names_staleness}"
    )


@then("the spine leaves the agent alone because it is already terminal")
def then_spine_leaves_terminal_alone(state_03) -> None:
    assert state_03["outcome"].closed is False, (
        "no-double-close precondition (DESIGN OQ-4): the stale terminal must fire "
        "ONLY when NO completed/blocked terminal record exists for "
        "(feature_id, slice_id); an agent that ALREADY reached a terminal state "
        "(a SliceCommitVerified completed / a SliceCommitBlockedTerminal blocked) "
        "must NOT be re-closed, even if its progress gap is large. A check that "
        "closes a stale agent regardless of an existing terminal would wrongly "
        "double-close here. "
        f"Got closed={state_03['outcome'].closed}, "
        f"names_staleness={state_03['outcome'].names_staleness}"
    )
