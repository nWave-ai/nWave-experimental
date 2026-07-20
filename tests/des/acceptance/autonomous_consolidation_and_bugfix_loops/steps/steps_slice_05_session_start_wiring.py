"""Step bodies for autonomous-consolidation-and-bugfix-loops slice-05
(a session starting fires every pending autonomous-loop tick, fail-open).

Mandate-12 criterion 3: every step body is <=2 statements, ends in a single
`loop_tick_wiring_fixture.<method>(...)` call (or one assertion), and
contains zero control flow. All business logic (request seeding, hook
invocation, before/after ledger diffing, stderr inspection) lives in
`LoopTickWiringFixture` (composition_slice_05.py). The typed-parameter
lookup (`PENDING_TICK_PHRASE_TO_DOMAIN`) is the only dict indexing this file
performs.

Mandate 8: every state-mutating outcome assertion goes through
`assert_state_delta(before, after, universe, expected)` from
`tests.common.state_delta`. The "before" snapshot is the well-defined ZERO
state (`_ZERO_OUTCOME_SNAPSHOT`) -- every scenario starts a FRESH fixture
(fresh tmp_path, fresh per-domain ledgers), so "nothing has ticked yet" is
provably the baseline without a separate snapshot-capturing step (mirrors
slice-03's `_ZERO_OUTCOME_SNAPSHOT` idiom). Universe entries are the
flattened, port-exposed observables on `LoopTickWiringOutcome` -- never
stdin/stdout/stderr capture buffers, never the raw JSON request bytes, never
the raw ledger path.

Mandate 9 v2: layer 3/4 (real filesystem + real ledger JSONL + real hook
invocation against tmp_path, @real-io) => example-only. PBT machinery is
intentionally NOT imported (Mandate 11 -- sad paths enumerated explicitly);
density comes from the Scenario Outline `Examples:` table (AT-24) over the
domain axis instead.

Mandate-13: ATs drive through the production SessionStart driving port (the
real `handle_session_start` hook) -- NEVER a direct `des.domain.*` /
`des.cli.*` invocation in test bodies.
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from tests.common.state_delta import assert_state_delta, set_to

from .domain_types_slice_05 import (
    LoopTickDomain,
    malformed_known_feature_tick,
    nameless_tick,
    well_formed_tick,
)


# --- Domain-phrase DSL (Mandate-12) -----------------------------------------

PENDING_TICK_PHRASE_TO_DOMAIN: dict[str, LoopTickDomain] = {
    "the pending work-exhausted tick": LoopTickDomain.WORK_EXHAUSTED,
    "the pending bugfix-pipeline tick": LoopTickDomain.BUGFIX_PIPELINE,
    "the pending consolidation-signal tick": LoopTickDomain.CONSOLIDATION_SIGNAL,
}


# --- Universe (Mandate 8): flattened, port-exposed observables only --------

TICKED_UNIVERSE = frozenset(
    {
        "outcome.ticked_work_exhausted",
        "outcome.ticked_bugfix_pipeline",
        "outcome.ticked_consolidation_signal",
    }
)

EXIT_UNIVERSE = frozenset({"outcome.exit_code"})

ATTEMPT_FAILED_UNIVERSE = frozenset(
    {
        "outcome.attempt_failed_work_exhausted",
        "outcome.attempt_failed_bugfix_pipeline",
        "outcome.attempt_failed_consolidation_signal",
    }
)

NAMELESS_UNIVERSE = frozenset(
    {
        "outcome.ticked_consolidation_signal",
        "outcome.attempt_failed_consolidation_signal",
        "outcome.stderr_mentions_consolidation_signal",
    }
)

# The well-defined ZERO baseline every fresh fixture starts from -- no hook
# invocation has fired yet, so every observable is its own "nothing
# happened" value (mirrors slice-03's `_ZERO_OUTCOME_SNAPSHOT`).
_ZERO_OUTCOME_SNAPSHOT = {
    "outcome.exit_code": None,
    "outcome.ticked_work_exhausted": False,
    "outcome.ticked_bugfix_pipeline": False,
    "outcome.ticked_consolidation_signal": False,
    "outcome.attempt_failed_work_exhausted": False,
    "outcome.attempt_failed_bugfix_pipeline": False,
    "outcome.attempt_failed_consolidation_signal": False,
    "outcome.stderr_mentions_work_exhausted": False,
    "outcome.stderr_mentions_bugfix_pipeline": False,
    "outcome.stderr_mentions_consolidation_signal": False,
}


def _snapshot(outcome) -> dict:
    """Flattened universe snapshot of every observable this slice's Thens
    read. Pure function.
    """
    return {
        "outcome.exit_code": outcome.exit_code,
        "outcome.ticked_work_exhausted": outcome.ticked[LoopTickDomain.WORK_EXHAUSTED],
        "outcome.ticked_bugfix_pipeline": outcome.ticked[
            LoopTickDomain.BUGFIX_PIPELINE
        ],
        "outcome.ticked_consolidation_signal": outcome.ticked[
            LoopTickDomain.CONSOLIDATION_SIGNAL
        ],
        "outcome.attempt_failed_work_exhausted": outcome.attempt_failed[
            LoopTickDomain.WORK_EXHAUSTED
        ],
        "outcome.attempt_failed_bugfix_pipeline": outcome.attempt_failed[
            LoopTickDomain.BUGFIX_PIPELINE
        ],
        "outcome.attempt_failed_consolidation_signal": outcome.attempt_failed[
            LoopTickDomain.CONSOLIDATION_SIGNAL
        ],
        "outcome.stderr_mentions_work_exhausted": outcome.stderr_mentions_domain[
            LoopTickDomain.WORK_EXHAUSTED
        ],
        "outcome.stderr_mentions_bugfix_pipeline": outcome.stderr_mentions_domain[
            LoopTickDomain.BUGFIX_PIPELINE
        ],
        "outcome.stderr_mentions_consolidation_signal": (
            outcome.stderr_mentions_domain[LoopTickDomain.CONSOLIDATION_SIGNAL]
        ),
    }


def _before(universe: frozenset) -> dict:
    return {k: _ZERO_OUTCOME_SNAPSHOT[k] for k in universe}


def _after(state: dict, universe: frozenset) -> dict:
    return {k: _snapshot(state["outcome"])[k] for k in universe}


# --- Given -------------------------------------------------------------


@given(
    "an operator has left a pending work-exhausted tick, a pending "
    "bugfix-pipeline tick, and a pending consolidation-signal tick from a "
    "prior loop iteration"
)
def given_all_three_pending(loop_tick_wiring_fixture) -> None:
    for domain in LoopTickDomain:
        loop_tick_wiring_fixture.seed(well_formed_tick(domain))


@given(
    parsers.parse(
        "an operator has left only {pending_tick} from a prior loop iteration"
    )
)
def given_only_one_pending(loop_tick_wiring_fixture, state_05, pending_tick) -> None:
    domain = PENDING_TICK_PHRASE_TO_DOMAIN[pending_tick]
    state_05["only_domain"] = domain
    loop_tick_wiring_fixture.seed(well_formed_tick(domain))


@given("an operator's prior loop iteration left no pending loop tick behind")
def given_none_pending() -> None:
    """No-op narrative precondition -- a fresh `.nwave/` carries no request
    files by construction (Pillar 2 chained narrative, not state setup).
    """


@given(
    "an operator has left a pending work-exhausted tick, a pending "
    "bugfix-pipeline tick that is missing what it must do, and a pending "
    "consolidation-signal tick from a prior loop iteration"
)
def given_malformed_bugfix_pending(loop_tick_wiring_fixture, state_05) -> None:
    state_05["broken_domain"] = LoopTickDomain.BUGFIX_PIPELINE
    loop_tick_wiring_fixture.seed(well_formed_tick(LoopTickDomain.WORK_EXHAUSTED))
    loop_tick_wiring_fixture.seed(
        malformed_known_feature_tick(LoopTickDomain.BUGFIX_PIPELINE)
    )
    loop_tick_wiring_fixture.seed(well_formed_tick(LoopTickDomain.CONSOLIDATION_SIGNAL))


@given(
    "an operator has left a pending work-exhausted tick, a pending "
    "bugfix-pipeline tick, and a pending consolidation-signal tick with no "
    "feature named from a prior loop iteration"
)
def given_nameless_consolidation_pending(loop_tick_wiring_fixture, state_05) -> None:
    state_05["broken_domain"] = LoopTickDomain.CONSOLIDATION_SIGNAL
    loop_tick_wiring_fixture.seed(well_formed_tick(LoopTickDomain.WORK_EXHAUSTED))
    loop_tick_wiring_fixture.seed(well_formed_tick(LoopTickDomain.BUGFIX_PIPELINE))
    loop_tick_wiring_fixture.seed(nameless_tick(LoopTickDomain.CONSOLIDATION_SIGNAL))


# --- When ---------------------------------------------------------------


@when("the operator's session starts")
def when_session_starts(loop_tick_wiring_fixture, state_05) -> None:
    state_05["outcome"] = loop_tick_wiring_fixture.fire_session_start()


# --- Then ------------------------------------------------------------------


@then("all three pending loop ticks fire exactly once")
def then_all_three_ticked(state_05) -> None:
    assert_state_delta(
        before=_before(TICKED_UNIVERSE),
        after=_after(state_05, TICKED_UNIVERSE),
        universe=TICKED_UNIVERSE,
        expected={
            "outcome.ticked_work_exhausted": set_to(True),
            "outcome.ticked_bugfix_pipeline": set_to(True),
            "outcome.ticked_consolidation_signal": set_to(True),
        },
    )


@then("the session-start hook still returns success")
def then_hook_returns_success(state_05) -> None:
    assert_state_delta(
        before=_before(EXIT_UNIVERSE),
        after=_after(state_05, EXIT_UNIVERSE),
        universe=EXIT_UNIVERSE,
        expected={"outcome.exit_code": set_to(0)},
    )


@then(parsers.parse("only {pending_tick} fires"))
def then_only_one_ticked(state_05, pending_tick) -> None:
    only_domain = PENDING_TICK_PHRASE_TO_DOMAIN[pending_tick]
    expected = {
        f"outcome.ticked_{d.value.replace('-', '_')}": set_to(d == only_domain)
        for d in LoopTickDomain
    }
    assert_state_delta(
        before=_before(TICKED_UNIVERSE),
        after=_after(state_05, TICKED_UNIVERSE),
        universe=TICKED_UNIVERSE,
        expected=expected,
    )


@then("no loop tick fires")
def then_no_tick_fired(state_05) -> None:
    assert_state_delta(
        before=_before(TICKED_UNIVERSE),
        after=_after(state_05, TICKED_UNIVERSE),
        universe=TICKED_UNIVERSE,
        expected={
            "outcome.ticked_work_exhausted": set_to(False),
            "outcome.ticked_bugfix_pipeline": set_to(False),
            "outcome.ticked_consolidation_signal": set_to(False),
        },
    )


@then(
    "the malformed bugfix-pipeline tick honestly records that its attempt "
    "failed, never silently"
)
def then_malformed_attempt_failed(state_05) -> None:
    assert_state_delta(
        before=_before(ATTEMPT_FAILED_UNIVERSE),
        after=_after(state_05, ATTEMPT_FAILED_UNIVERSE),
        universe=ATTEMPT_FAILED_UNIVERSE,
        expected={
            "outcome.attempt_failed_work_exhausted": set_to(False),
            "outcome.attempt_failed_bugfix_pipeline": set_to(True),
            "outcome.attempt_failed_consolidation_signal": set_to(False),
        },
    )


@then("the other two pending loop ticks still fire")
def then_other_two_still_fire(state_05) -> None:
    broken = state_05["broken_domain"]
    expected = {
        f"outcome.ticked_{d.value.replace('-', '_')}": set_to(d != broken)
        for d in LoopTickDomain
    }
    assert_state_delta(
        before=_before(TICKED_UNIVERSE),
        after=_after(state_05, TICKED_UNIVERSE),
        universe=TICKED_UNIVERSE,
        expected=expected,
    )


@then(
    "the nameless consolidation-signal tick fails open silently to the "
    "operator's terminal only, with no attempt recorded"
)
def then_nameless_fails_open_to_terminal(state_05) -> None:
    assert_state_delta(
        before=_before(NAMELESS_UNIVERSE),
        after=_after(state_05, NAMELESS_UNIVERSE),
        universe=NAMELESS_UNIVERSE,
        expected={
            "outcome.ticked_consolidation_signal": set_to(False),
            "outcome.attempt_failed_consolidation_signal": set_to(False),
            "outcome.stderr_mentions_consolidation_signal": set_to(True),
        },
    )
