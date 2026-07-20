"""Step bodies for autonomous-consolidation-and-bugfix-loops slice-02
(an exhausted loop stops instead of idle-holding).

Mandate-12 criterion 3: every step body is <=2 statements, ends in a single
`escalation_fixture.<method>(...)` call (or one assertion), and contains zero
control flow (`if`/`for`/`while`/`try`). All sequencing/arithmetic logic
(CSV parsing, cadence stepping, the STOP/ESCALATE-then-retick precondition)
lives in `EscalationFixture` (composition_slice_02.py). The typed-parameter
lookups (`QUEUE_STATE_BY_GIVEN_PHRASE`, `BOOL_BY_YES_NO`) are the only dict
indexing this file performs.

Mandate 8: every state-mutating outcome assertion goes through
`assert_state_delta(before, after, universe, expected)` from
`tests.common.state_delta`. The "before" snapshot is the well-defined ZERO
state (`_ZERO_OUTCOME_SNAPSHOT`) -- every scenario starts a FRESH fixture
(fresh tmp_path ledger), so "nothing has fired yet" is provably the baseline
without a separate snapshot-capturing step. Universe entries are port-exposed
observables on `EscalationOutcome` -- never Popen handles, never argv lists,
never the raw ledger path.

Mandate 9 v2: layer 3/4 (real filesystem + real ledger JSONL + real in-process
CLI invocation against tmp_path, @real-io) => example-only. PBT machinery is
intentionally NOT imported (Mandate 11 -- sad paths enumerated explicitly);
density comes from Scenario Outline `Examples:` tables over the time-ladder +
cadence + resolution-timing space instead.

Mandate-13: ATs drive through the production `des work-exhausted-tick` driving
port (the real `des.cli.work_exhausted_tick.main` entry) -- NEVER a direct
`from des.domain.work_exhausted_ladder import evaluate_and_record` invocation
in test bodies (that seam does not even exist yet -- it is DELIVER's job).
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from tests.common.state_delta import assert_state_delta, set_to

from .domain_types_slice_02 import BOOL_BY_YES_NO, QUEUE_STATE_BY_GIVEN_PHRASE


# --- Universe (Mandate 8): port-exposed observables only -------------------

LADDER_UNIVERSE = frozenset(
    {
        "outcome.first_warning_fired",
        "outcome.first_warning_within_ceiling",
        "outcome.second_warning_fired",
        "outcome.second_warning_within_ceiling",
        "outcome.stop_escalate_fired",
        "outcome.stop_escalate_within_ceiling",
        "outcome.reason_named",
    }
)

TIMESTAMPS_PROOF_UNIVERSE = frozenset(
    {
        "outcome.ledger_proves_ladder_from_timestamps_alone",
        "outcome.stop_escalate_fired",
    }
)

WINDOW_RESOLVE_UNIVERSE = frozenset(
    {"outcome.window_resolved", "outcome.stop_escalate_fired"}
)

FIRST_WARNING_ONLY_UNIVERSE = frozenset(
    {"outcome.first_warning_fired", "outcome.first_warning_within_ceiling"}
)

NO_QUIET_UNSTOP_UNIVERSE = frozenset({"outcome.new_record_count"})

# The well-defined ZERO baseline every fresh fixture starts from -- no ticks
# have fired anything yet, so every observable is its own "nothing happened"
# value. Reused as the `before` half of every `assert_state_delta` call
# below (no separate before-snapshot step is needed: the fixture is provably
# fresh at the start of each scenario).
_ZERO_OUTCOME_SNAPSHOT = {
    "outcome.first_warning_fired": False,
    "outcome.first_warning_within_ceiling": False,
    "outcome.second_warning_fired": False,
    "outcome.second_warning_within_ceiling": False,
    "outcome.stop_escalate_fired": False,
    "outcome.stop_escalate_within_ceiling": False,
    "outcome.reason_named": False,
    "outcome.window_resolved": False,
    "outcome.ledger_proves_ladder_from_timestamps_alone": True,
    "outcome.new_record_count": 0,
}


def _snapshot(outcome) -> dict:
    """Universe snapshot of every observable this slice's Thens read. Pure."""
    return {
        "outcome.first_warning_fired": outcome.first_warning_fired,
        "outcome.first_warning_within_ceiling": outcome.first_warning_within_ceiling,
        "outcome.second_warning_fired": outcome.second_warning_fired,
        "outcome.second_warning_within_ceiling": outcome.second_warning_within_ceiling,
        "outcome.stop_escalate_fired": outcome.stop_escalate_fired,
        "outcome.stop_escalate_within_ceiling": outcome.stop_escalate_within_ceiling,
        "outcome.reason_named": outcome.reason_named,
        "outcome.window_resolved": outcome.window_resolved,
        "outcome.ledger_proves_ladder_from_timestamps_alone": (
            outcome.ledger_proves_ladder_from_timestamps_alone
        ),
        "outcome.new_record_count": outcome.new_record_count,
    }


def _before(universe: frozenset) -> dict:
    return {k: _ZERO_OUTCOME_SNAPSHOT[k] for k in universe}


# --- Given ------------------------------------------------------------------


@given(parsers.parse("a loop whose queue {queue_phrase} at minute {minute:d}"))
def given_loop_queue_state(state_02, queue_phrase, minute) -> None:
    state_02["queue_state"] = QUEUE_STATE_BY_GIVEN_PHRASE[queue_phrase]
    state_02["open_at_minute"] = minute


@given(
    parsers.parse(
        "the loop has already escalated to STOP/ESCALATE by minute {minute:d}"
    )
)
def given_already_escalated(escalation_fixture, state_02, minute) -> None:
    state_02["precondition_outcome"] = escalation_fixture.escalate_to_stop(
        state_02["queue_state"], state_02["open_at_minute"], minute
    )


# --- When ---------------------------------------------------------------


@when(parsers.parse("the loop ticks again at minute {minute:d}"))
def when_ticks_again(escalation_fixture, state_02, minute) -> None:
    state_02["outcome"] = escalation_fixture.run_ladder_sequence(
        [
            (state_02["queue_state"], state_02["open_at_minute"]),
            (state_02["queue_state"], minute),
        ]
    )


@when(parsers.parse('the loop ticks in turn at minutes "{minutes_csv}"'))
def when_ticks_in_turn(escalation_fixture, state_02, minutes_csv) -> None:
    state_02["outcome"] = escalation_fixture.tick_in_turn(
        state_02["queue_state"], state_02["open_at_minute"], minutes_csv
    )


@when(parsers.parse("the loop ticks every {cadence:d} minutes until minute {until:d}"))
def when_ticks_at_cadence(escalation_fixture, state_02, cadence, until) -> None:
    state_02["outcome"] = escalation_fixture.tick_at_cadence_until(
        state_02["queue_state"], state_02["open_at_minute"], cadence, until
    )


@when(
    parsers.parse(
        "the loop ticks at minute {m1:d}, minute {m2:d} and then a freshly "
        "unblocked item appears at minute {m3:d}"
    )
)
def when_ticks_then_resolves(escalation_fixture, state_02, m1, m2, m3) -> None:
    state_02["outcome"] = escalation_fixture.resolve_after(
        state_02["queue_state"], state_02["open_at_minute"], m1, m2, m3
    )


@when(
    parsers.parse(
        "the loop ticks again at minute {minute:d} with the queue still empty"
    )
)
def when_ticks_again_post_stop(escalation_fixture, state_02, minute) -> None:
    state_02["outcome"] = escalation_fixture.fire_additional_tick(
        queue_state=state_02["queue_state"], at_minute=minute
    )


# --- Then ------------------------------------------------------------------


@then(
    parsers.parse(
        'the ladder has fired FIRST WARNING "{first_warning}", SECOND WARNING '
        '"{second_warning}" and STOP/ESCALATE "{stop_escalate}" by that tick'
    )
)
def then_ladder_state_by_tick(
    state_02, first_warning, second_warning, stop_escalate
) -> None:
    fw, sw, se = (
        BOOL_BY_YES_NO[first_warning],
        BOOL_BY_YES_NO[second_warning],
        BOOL_BY_YES_NO[stop_escalate],
    )
    assert_state_delta(
        before=_before(LADDER_UNIVERSE),
        after={k: _snapshot(state_02["outcome"])[k] for k in LADDER_UNIVERSE},
        universe=LADDER_UNIVERSE,
        expected={
            "outcome.first_warning_fired": set_to(fw),
            "outcome.first_warning_within_ceiling": set_to(fw),
            "outcome.second_warning_fired": set_to(sw),
            "outcome.second_warning_within_ceiling": set_to(sw),
            "outcome.stop_escalate_fired": set_to(se),
            "outcome.stop_escalate_within_ceiling": set_to(se),
            "outcome.reason_named": set_to(fw or sw or se),
        },
    )


@then(
    "the ladder has fired FIRST WARNING, SECOND WARNING and STOP/ESCALATE by minute 46"
)
def then_full_ladder_fired_by_46(state_02) -> None:
    assert_state_delta(
        before=_before(LADDER_UNIVERSE),
        after={k: _snapshot(state_02["outcome"])[k] for k in LADDER_UNIVERSE},
        universe=LADDER_UNIVERSE,
        expected={
            "outcome.first_warning_fired": set_to(True),
            "outcome.first_warning_within_ceiling": set_to(True),
            "outcome.second_warning_fired": set_to(True),
            "outcome.second_warning_within_ceiling": set_to(True),
            "outcome.stop_escalate_fired": set_to(True),
            "outcome.stop_escalate_within_ceiling": set_to(True),
            "outcome.reason_named": set_to(True),
        },
    )


@then(
    "the ledger alone proves no exhausted window ran past 45 minutes without "
    "a STOP/ESCALATE record"
)
def then_ledger_proves_no_overrun(state_02) -> None:
    outcome = state_02["outcome"]
    assert_state_delta(
        before=_before(TIMESTAMPS_PROOF_UNIVERSE),
        after={k: _snapshot(outcome)[k] for k in TIMESTAMPS_PROOF_UNIVERSE},
        universe=TIMESTAMPS_PROOF_UNIVERSE,
        expected={
            "outcome.ledger_proves_ladder_from_timestamps_alone": set_to(True),
            "outcome.stop_escalate_fired": set_to(True),
        },
    )
    assert outcome.ledger_proves_ladder_from_timestamps_alone, (
        "D-2 negative-oracle (CRITICAL): an observer reading ONLY the ledger's "
        "own recorded timestamps -- zero knowledge of the loop's tick interval "
        "-- must be able to prove no exhausted-state window ran past the "
        "45-minute ceiling without a STOP/ESCALATE record. It could not. "
        f"Got stop_escalate_fired={outcome.stop_escalate_fired}, "
        f"new_record_count={outcome.new_record_count}."
    )


@then("the loop's window is resolved with no STOP/ESCALATE record ever fired")
def then_window_resolved_without_escalate(state_02) -> None:
    outcome = state_02["outcome"]
    assert_state_delta(
        before=_before(WINDOW_RESOLVE_UNIVERSE),
        after={k: _snapshot(outcome)[k] for k in WINDOW_RESOLVE_UNIVERSE},
        universe=WINDOW_RESOLVE_UNIVERSE,
        expected={
            "outcome.window_resolved": set_to(True),
            "outcome.stop_escalate_fired": set_to(False),
        },
    )


@then("the ladder fires FIRST WARNING exactly as it would for a genuinely empty queue")
def then_first_warning_on_malformed(state_02) -> None:
    outcome = state_02["outcome"]
    assert_state_delta(
        before=_before(FIRST_WARNING_ONLY_UNIVERSE),
        after={k: _snapshot(outcome)[k] for k in FIRST_WARNING_ONLY_UNIVERSE},
        universe=FIRST_WARNING_ONLY_UNIVERSE,
        expected={
            "outcome.first_warning_fired": set_to(True),
            "outcome.first_warning_within_ceiling": set_to(True),
        },
    )


@then("the loop appends no new record because a stale re-poll is not a fresh trigger")
def then_no_new_record_on_stale_repoll(state_02) -> None:
    outcome = state_02["outcome"]
    precondition = state_02["precondition_outcome"]
    # Discriminator (Closure Obligations, SILENCE/ABSENCE): a zero-new-
    # records reading is only MEANINGFUL if STOP/ESCALATE genuinely fired
    # during the Given precondition. Without this check, an
    # implementation that writes NOTHING AT ALL would pass this scenario
    # vacuously -- looked-and-genuinely-stopped is not the same as
    # never-actually-looked.
    assert precondition.stop_escalate_fired, (
        "D-8 discriminator (CRITICAL): this scenario's precondition is that "
        "the loop ALREADY reached STOP/ESCALATE by minute 45 -- that must be "
        "independently true before a 'no new records on re-tick' reading means "
        "anything. A ladder that never escalates at all would satisfy "
        "'zero new records' vacuously, which is the exact false-negative the "
        "discriminator mandate forbids. "
        f"Got precondition.stop_escalate_fired={precondition.stop_escalate_fired}."
    )
    assert_state_delta(
        before=_before(NO_QUIET_UNSTOP_UNIVERSE),
        after={k: _snapshot(outcome)[k] for k in NO_QUIET_UNSTOP_UNIVERSE},
        universe=NO_QUIET_UNSTOP_UNIVERSE,
        expected={"outcome.new_record_count": set_to(0)},
    )
    assert not outcome.resumed_without_fresh_trigger, (
        "D-2 negative-oracle (CRITICAL): a loop that already reached "
        "STOP/ESCALATE must NOT silently resume polling on a stale exhausted "
        "re-tick with no fresh triggering condition (a newly-unblocked item) "
        "-- 'a stop that quietly un-stops itself is the same failure mode in "
        f"disguise' (charter). Got resumed_without_fresh_trigger="
        f"{outcome.resumed_without_fresh_trigger}."
    )
