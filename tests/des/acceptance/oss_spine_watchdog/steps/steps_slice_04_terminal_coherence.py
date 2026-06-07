"""Step bodies for oss-spine-watchdog slice-04 (terminal-coherence feature-end-fix).

Mandate-12 criterion 3: every step body is ≤2 statements, ends in a single
`terminal_coherence_fixture.<method>(...)` call (or one assertion), and contains
zero control flow (`if`/`for`/`while`/`try`). All business logic lives in
`TerminalCoherenceFixture` (composition_slice_04.py).

Mandate 8: the state-mutating outcome assertion (AT-01, a durable terminal record
appended) goes through `assert_state_delta(before, after, universe, expected)` from
`tests.common.state_delta`. Universe entries are port-exposed observables on
`BoundedTerminalOutcome` / `CrossInvocationOutcome` — never Popen handles, never the
transcript JSONL bytes, never the raw ledger path (Mandate 8 — port-exposed
observables only).

Mandate 9 v2: layer 3/4 (real git repo + real ledger JSONL + real hook subprocess
against tmp_path, @real-io — the driven set includes a real filesystem adapter + a
real git subprocess + a real hook subprocess) → example-only. PBT machinery is
intentionally NOT imported (Mandate 11 — sad paths enumerated explicitly).

Mandate-13: ATs drive through the production SubagentStop driving port (the real
`handle_subagent_stop` hook subprocess) — NEVER a direct
`from des...subagent_stop_handler import _emit_bounded_block_terminal` (or
`_maybe_emit_stale_agent_closed`) invocation in test bodies. The composition fires
the hook over its JSON stdin protocol.
"""

from __future__ import annotations

from pytest_bdd import given, then, when

from tests.common.state_delta import assert_state_delta, set_to

from .domain_types_slice_04 import PriorTerminalKind


# --- Universe (Mandate 8): port-exposed observables only -----------------

BOUNDED_TERMINAL_UNIVERSE = frozenset(
    {
        "outcome.terminal_recorded",
        "outcome.blocked",
    }
)


def _bounded_snapshot(state: dict) -> dict:
    """Build a universe snapshot of the bounded-terminal observables. Pure function.

    Returns None sentinels for unobserved keys so the before-snapshot is
    well-defined before the hook fires.
    """
    outcome = state.get("outcome")
    return {
        "outcome.terminal_recorded": getattr(outcome, "terminal_recorded", None),
        "outcome.blocked": getattr(outcome, "blocked", None),
    }


# --- Given ----------------------------------------------------------------


@given("two prior identical exit-gate blocks are recorded for the slice and commit")
def given_two_prior_identical_blocks(terminal_coherence_fixture, state_04) -> None:
    state_04["before"] = _bounded_snapshot(state_04)


@given(
    "a returning agent gone stale whose only prior record is a re-fire block, not a terminal"
)
def given_stale_agent_with_non_terminal_block(
    terminal_coherence_fixture, state_04
) -> None:
    state_04["prior"] = PriorTerminalKind.NON_TERMINAL_BLOCK


@given("a returning agent gone stale that has already reached a completed terminal")
def given_stale_agent_with_genuine_terminal(
    terminal_coherence_fixture, state_04
) -> None:
    state_04["prior"] = PriorTerminalKind.GENUINE_TERMINAL


# --- When -----------------------------------------------------------------


@when("the spine evaluates the third identical exit-gate block for the same slice")
def when_spine_evaluates_third_block(terminal_coherence_fixture, state_04) -> None:
    terminal_coherence_fixture.build_blocking_commit()
    state_04["outcome"] = terminal_coherence_fixture.run_bounded_block_terminal()


@when("a later stale check evaluates the returning agent when the hook fires")
def when_later_stale_check_evaluates(terminal_coherence_fixture, state_04) -> None:
    terminal_coherence_fixture.build_returning_agent_repo()
    state_04["outcome"] = terminal_coherence_fixture.run_cross_invocation_stale_check(
        prior=state_04["prior"]
    )


# --- Then -----------------------------------------------------------------


@then("the spine writes a durable terminal record for the bounded-block terminal")
def then_spine_writes_durable_terminal_record(state_04) -> None:
    after = _bounded_snapshot(state_04)
    assert_state_delta(
        before={k: state_04["before"][k] for k in BOUNDED_TERMINAL_UNIVERSE},
        after={k: after[k] for k in BOUNDED_TERMINAL_UNIVERSE},
        universe=BOUNDED_TERMINAL_UNIVERSE,
        expected={
            "outcome.terminal_recorded": set_to(True),
            "outcome.blocked": set_to(False),
        },
    )


@then("the spine closes the stuck agent because a re-fire block is not a terminal")
def then_spine_closes_stuck_agent(state_04) -> None:
    assert state_04["outcome"].closed is True, (
        "BLOCKER-3 (R-69-B): the stale-check no-double-close precondition must key "
        "on GENUINE terminals only. A regular SliceCommitBlocked is the NON-terminal "
        "re-fire record (2 precede every bounded-block) — NOT a terminal. A returning "
        "agent gone stale whose only prior record is a re-fire block, with no genuine "
        "terminal, MUST be closed (StaleAgentClosed). Today _EXISTING_TERMINAL_EVENTS "
        "includes SliceCommitBlocked, so the stale check mistakes the historical block "
        "for a terminal and WRONGLY LEAVES THE STUCK AGENT ALONE (the silent-hang "
        "false-negative the feature exists to kill). "
        f"Got closed={state_04['outcome'].closed}, blocked={state_04['outcome'].blocked}"
    )


@then("the spine leaves the agent alone because it has already reached a terminal")
def then_spine_leaves_genuine_terminal_alone(state_04) -> None:
    assert state_04["outcome"].closed is False, (
        "anti-vacuity pin (no-double-close PRESERVED): an agent that has already "
        "reached a GENUINE terminal (SliceCommitVerified completed) must NOT be "
        "re-closed even when its progress gap is stale. The slice-04 re-key narrows "
        "_EXISTING_TERMINAL_EVENTS onto genuine terminals — it must NOT drop the "
        "precondition entirely. A re-key that always-closes on a stale gap would "
        "wrongly close here. This pin guards the re-key against over-correction. "
        f"Got closed={state_04['outcome'].closed}, blocked={state_04['outcome'].blocked}"
    )
