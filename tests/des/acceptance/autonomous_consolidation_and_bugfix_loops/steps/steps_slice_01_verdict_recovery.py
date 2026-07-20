"""Step bodies for autonomous-consolidation-and-bugfix-loops slice-01
(a stale-closed agent recovers its own verdict).

Mandate-12 criterion 3: every step body is <=2 statements, ends in a single
`recovery_fixture.<method>(...)` call (or one assertion), and contains zero
control flow (`if`/`for`/`while`/`try`). All business logic lives in
`RecoveryFixture` (composition_slice_01.py). The typed-parameter lookup
(`TRANSCRIPT_CASE_BY_PHRASE`) is the single dict indexing this file performs.

Mandate 8: the state-mutating outcome assertion goes through
`assert_state_delta(before, after, universe, expected)` from
`tests.common.state_delta`. Universe entries are port-exposed observables on
`RecoveryOutcome` -- never Popen handles, never the transcript JSONL bytes,
never the raw ledger path.

Mandate 9 v2: layer 3/4 (real git repo + real ledger JSONL + real hook
invocation against tmp_path, @real-io) => example-only. PBT machinery is
intentionally NOT imported (Mandate 11 -- sad paths enumerated explicitly);
density comes from the Scenario Outline `Examples:` tables instead.

Mandate-13: ATs drive through the production SubagentStop driving port (the
real `handle_subagent_stop` hook) -- NEVER a direct
`from des...subagent_stop_handler import _maybe_emit_stale_agent_closed`
invocation in test bodies.
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from tests.common.state_delta import assert_state_delta, set_to

from .domain_types_slice_01 import TRANSCRIPT_CASE_BY_PHRASE


# --- Universe (Mandate 8): port-exposed observables only -------------------

RECOVERY_UNIVERSE = frozenset(
    {
        "outcome.closed",
        "outcome.paired_recovery",
        "outcome.recovered",
        "outcome.recovered_verdict",
        "outcome.distinguishable",
        "outcome.durable_on_reread",
    }
)

LEDGER_UNCHANGED_UNIVERSE = frozenset({"outcome.new_record_count"})


def _recovery_snapshot(state: dict) -> dict:
    """Universe snapshot of the recovery observables. Pure function.

    Returns None sentinels for unobserved keys so the before-snapshot is
    well-defined before the hook fires.
    """
    outcome = state.get("outcome")
    return {
        "outcome.closed": getattr(outcome, "closed", None),
        "outcome.paired_recovery": getattr(outcome, "paired_recovery", None),
        "outcome.recovered": getattr(outcome, "recovered", None),
        "outcome.recovered_verdict": getattr(outcome, "recovered_verdict", None),
        "outcome.distinguishable": getattr(outcome, "distinguishable", None),
        "outcome.durable_on_reread": getattr(outcome, "durable_on_reread", None),
        "outcome.new_record_count": getattr(outcome, "new_record_count", None),
    }


# --- Given ------------------------------------------------------------------


@given(parsers.parse("a stale-closed agent whose transcript {transcript_state}"))
def given_stale_agent_with_transcript(
    recovery_fixture, state_01, transcript_state
) -> None:
    state_01["case"] = TRANSCRIPT_CASE_BY_PHRASE[transcript_state]


@given("the spine has already closed and recovered this agent once")
def given_already_closed_and_recovered(recovery_fixture, state_01) -> None:
    state_01["outcome"] = recovery_fixture.run_recovery_check(case=state_01["case"])


# --- When ---------------------------------------------------------------


@when("the spine evaluates the returning agent when the hook fires")
def when_spine_evaluates_returning_agent(recovery_fixture, state_01) -> None:
    state_01["before"] = _recovery_snapshot(state_01)


@when("the spine finishes evaluating the returning agent")
def when_spine_finishes_evaluating(recovery_fixture, state_01) -> None:
    state_01["outcome"] = recovery_fixture.run_recovery_check(case=state_01["case"])


@when("the spine evaluates the returning agent again when the hook re-fires")
def when_spine_refires_on_already_closed_agent(recovery_fixture, state_01) -> None:
    state_01["before"] = _recovery_snapshot(state_01)
    state_01["outcome"] = recovery_fixture.refire_after_recovery()


# --- Then ------------------------------------------------------------------


@then(
    parsers.parse(
        'the spine closes the agent loud and pairs it, same tick, with a recovered verdict of "{expected_verdict}"'
    )
)
def then_closed_and_paired_with_verdict(state_01, expected_verdict) -> None:
    after = _recovery_snapshot(state_01)
    assert_state_delta(
        before={k: state_01["before"][k] for k in RECOVERY_UNIVERSE},
        after={k: after[k] for k in RECOVERY_UNIVERSE},
        universe=RECOVERY_UNIVERSE,
        expected={
            "outcome.closed": set_to(True),
            "outcome.paired_recovery": set_to(True),
            "outcome.recovered": set_to(True),
            "outcome.recovered_verdict": set_to(expected_verdict),
            "outcome.distinguishable": set_to(True),
            "outcome.durable_on_reread": set_to(True),
        },
    )


@then(
    "the recovered verdict is durable and marked transcript-recovered, not agent-reported"
)
def then_durable_and_marked_transcript_recovered(state_01) -> None:
    outcome = state_01["outcome"]
    assert outcome.distinguishable and outcome.durable_on_reread, (
        "charter Positive-2: the recovery record must be durable (survives a "
        "fresh re-read of the ledger) AND clearly marked transcript-recovered "
        "-- distinguishable from a normal agent-reported completed terminal. "
        f"Got distinguishable={outcome.distinguishable}, "
        f"durable_on_reread={outcome.durable_on_reread}."
    )


@then(
    "the spine closes the agent loud and pairs it, same tick, with an honest could-not-recover record"
)
def then_closed_and_paired_with_honest_failure(state_01) -> None:
    after = _recovery_snapshot(state_01)
    assert_state_delta(
        before={k: state_01["before"][k] for k in RECOVERY_UNIVERSE},
        after={k: after[k] for k in RECOVERY_UNIVERSE},
        universe=RECOVERY_UNIVERSE,
        expected={
            "outcome.closed": set_to(True),
            "outcome.paired_recovery": set_to(True),
            "outcome.recovered": set_to(False),
            "outcome.recovered_verdict": set_to(None),
            "outcome.distinguishable": set_to(True),
            "outcome.durable_on_reread": set_to(True),
        },
    )


@then("no fabricated verdict is ever recorded for this agent")
def then_no_fabricated_verdict(state_01) -> None:
    outcome = state_01["outcome"]
    assert outcome.recovered_verdict is None and outcome.unrecoverable_reason, (
        "D-8 negative-oracle (CRITICAL): an ambiguous/empty/corrupted "
        "transcript must NEVER yield a guessed verdict -- the recovery record "
        "must carry a None `recovered_verdict` AND a non-empty honest "
        "`unrecoverable_reason` explaining WHY no verdict could be recovered. "
        f"Got recovered_verdict={outcome.recovered_verdict!r}, "
        f"unrecoverable_reason={outcome.unrecoverable_reason!r}."
    )


@then(
    "the spine leaves the ledger byte-for-byte unchanged because the agent is already closed and recovered"
)
def then_ledger_unchanged_on_refire(state_01) -> None:
    after = _recovery_snapshot(state_01)
    assert_state_delta(
        before={k: state_01["before"][k] for k in LEDGER_UNCHANGED_UNIVERSE},
        after={k: after[k] for k in LEDGER_UNCHANGED_UNIVERSE},
        universe=LEDGER_UNCHANGED_UNIVERSE,
        expected={"outcome.new_record_count": set_to(0)},
    )
