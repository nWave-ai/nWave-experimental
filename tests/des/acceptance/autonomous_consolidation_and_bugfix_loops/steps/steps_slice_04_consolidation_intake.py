"""Step bodies for autonomous-consolidation-and-bugfix-loops slice-04
(trunk-health signals become queue items that never vanish).

Mandate-12 criterion 3: every Given/When step body is <=2 statements, ends
in a single `intake_fixture.<method>(...)` call, and contains zero control
flow (`if`/`for`/`while`/`try`). The typed-parameter lookup is limited to
reading `state_04["signal"]` (the last-detected signal, set by the prior
When step -- Pillar 2 chained narrative: "its queue item" in AT-19 refers
back to the signal the previous Gherkin line just detected). Then steps
follow the slice-03 precedent shape: sample the outcome, then
`assert_state_delta` + explicit asserts -- the outcome-interpretation +
assertion work an oracle inherently needs, not business logic.

Mandate 8: every state-mutating outcome assertion goes through
`assert_state_delta(before, after, universe, expected)` from
`tests.common.state_delta`. The "before" snapshot is the well-defined ZERO
state (`_ZERO_OUTCOME_SNAPSHOT`) -- every scenario starts a FRESH fixture
(fresh tmp_path ledger), so "nothing has fired yet" is provably the baseline
without a separate snapshot-capturing step. Universe entries are port-exposed
observables on `IntakeOutcome` -- never Popen handles, never argv lists,
never the raw ledger path, never the derived defect_id string.

Mandate 9 v2: layer 3/4 (real filesystem + real ledger JSONL + real
in-process CLI invocation against tmp_path, @real-io) => example-only. PBT
machinery is intentionally NOT imported (Mandate 11 -- sad paths enumerated
explicitly); density comes from the Scenario Outline `Examples:` table over
the signal-type axis (AT-17) instead.

Mandate-13: ATs drive through the production `des consolidation-signal-tick`
driving port (the real `des.cli.consolidation_signal_tick.main` entry) --
NEVER a direct
`from des.domain.consolidation_queue_intake import intake_signal` invocation
in test bodies (that seam does not even exist yet -- it is DELIVER's job).
AT-19 additionally drives the SIBLING slice-03 driving port
(`des.cli.bugfix_pipeline_tick.main`) directly -- both are production CLI
entries, never a domain-layer import.
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from tests.common.state_delta import assert_state_delta, set_to


# --- Universe (Mandate 8): port-exposed observables only -------------------

SIGNAL_TRACEABLE_UNIVERSE = frozenset(
    {"outcome.queue_item_count", "outcome.traceable_to_signal"}
)

MULTI_SIGNAL_UNIVERSE = frozenset({"outcome.queue_item_count"})

FULL_CHAIN_UNIVERSE = frozenset(
    {"outcome.full_chain_traceable", "outcome.slice_commit_verified_present"}
)

REJECTED_UNIVERSE = frozenset(
    {
        "outcome.intake_rejected",
        "outcome.rejection_reason_named",
        "outcome.queue_item_count",
    }
)

# EXAMINE fix (Vera FAIL, real-CLI-surface defect): the CLI-facing surface
# itself must observe a rejection, not merely the ledger -- a caller who
# never reads the ledger must still see the rejection fail loudly (D-8).
CLI_SELF_EXPLAINING_UNIVERSE = frozenset(
    {
        "outcome.cli_exit_code",
        "outcome.cli_output_names_unsupported_type",
        "outcome.cli_output_names_supported_set",
    }
)

# The well-defined ZERO baseline every fresh fixture starts from -- no ticks
# have fired anything yet, so every observable is its own "nothing happened"
# value. Reused as the `before` half of every `assert_state_delta` call
# below (no separate before-snapshot step is needed: the fixture is provably
# fresh at the start of each scenario).
_ZERO_OUTCOME_SNAPSHOT = {
    "outcome.queue_item_count": 0,
    "outcome.traceable_to_signal": False,
    "outcome.full_chain_traceable": False,
    "outcome.slice_commit_verified_present": False,
    "outcome.intake_rejected": False,
    "outcome.rejection_reason_named": False,
    "outcome.cli_exit_code": 0,
    "outcome.cli_output_names_unsupported_type": False,
    "outcome.cli_output_names_supported_set": False,
}


def _snapshot(outcome) -> dict:
    """Universe snapshot of every observable this slice's Thens read. Pure."""
    return {
        "outcome.queue_item_count": outcome.queue_item_count,
        "outcome.traceable_to_signal": outcome.traceable_to_signal,
        "outcome.full_chain_traceable": outcome.full_chain_traceable,
        "outcome.slice_commit_verified_present": (
            outcome.slice_commit_verified_present
        ),
        "outcome.intake_rejected": outcome.intake_rejected,
        "outcome.rejection_reason_named": outcome.rejection_reason_named,
        "outcome.cli_exit_code": outcome.cli_exit_code,
        "outcome.cli_output_names_unsupported_type": (
            outcome.cli_output_names_unsupported_type
        ),
        "outcome.cli_output_names_supported_set": (
            outcome.cli_output_names_supported_set
        ),
    }


def _before(universe: frozenset) -> dict:
    return {k: _ZERO_OUTCOME_SNAPSHOT[k] for k in universe}


# --- Given -------------------------------------------------------------


@given("a fresh consolidation intake")
def given_fresh_intake() -> None:
    """No-op narrative precondition -- ``intake_fixture`` is already a
    fresh, empty ledger per scenario (fresh ``tmp_path``); this step exists
    for Gherkin readability (Pillar 2 chained narrative), not state setup.
    """


# --- When ----------------------------------------------------------------


@when(
    parsers.parse(
        'a "{signal_type}" signal for "{signal_key}" is detected at minute {minute:d}'
    )
)
def when_signal_detected(
    state_04, intake_fixture, signal_type, signal_key, minute
) -> None:
    state_04["signal"] = (signal_type, signal_key)
    intake_fixture.detect_signal(signal_type, signal_key, minute)


@when(
    parsers.parse(
        'the same "{signal_type}" signal for "{signal_key}" is detected '
        "again at minute {minute:d}"
    )
)
def when_signal_detected_again(
    state_04, intake_fixture, signal_type, signal_key, minute
) -> None:
    state_04["signal"] = (signal_type, signal_key)
    intake_fixture.detect_signal(signal_type, signal_key, minute)


@when(
    parsers.parse(
        'an unsupported "{signal_type}" signal for "{signal_key}" is '
        "detected at minute {minute:d}"
    )
)
def when_unsupported_signal_detected(
    state_04, intake_fixture, signal_type, signal_key, minute
) -> None:
    state_04["signal"] = (signal_type, signal_key)
    state_04["outcome"] = intake_fixture.detect_unsupported_signal_and_capture_cli(
        signal_type, signal_key, minute
    )


@when(
    parsers.parse(
        "its queue item walks the rest of the shared pipeline to "
        "commit-slice starting at minute {minute:d}"
    )
)
def when_queue_item_walks_rest_of_pipeline(state_04, intake_fixture, minute) -> None:
    signal_type, signal_key = state_04["signal"]
    state_04["outcome"] = intake_fixture.drive_rest_of_shared_pipeline(
        signal_type, signal_key, minute
    )


# --- Then ------------------------------------------------------------------


@then(
    parsers.parse(
        "sampled at minute {minute:d}, that signal produced exactly one "
        "queue item traceable back to it"
    )
)
def then_signal_traceable(intake_fixture, state_04, minute) -> None:
    signal_type, signal_key = state_04["signal"]
    outcome = intake_fixture.sample_for_signal(signal_type, signal_key, minute)
    assert_state_delta(
        before=_before(SIGNAL_TRACEABLE_UNIVERSE),
        after={k: _snapshot(outcome)[k] for k in SIGNAL_TRACEABLE_UNIVERSE},
        universe=SIGNAL_TRACEABLE_UNIVERSE,
        expected={
            "outcome.queue_item_count": set_to(1),
            "outcome.traceable_to_signal": set_to(True),
        },
    )


@then(
    parsers.parse(
        "sampled at minute {minute:d}, exactly {count:d} distinct queue "
        "items are observed, one per {noun}"
    )
)
def then_distinct_queue_items_observed(intake_fixture, minute, count, noun) -> None:
    outcome = intake_fixture.sample_all_signals(minute)
    assert_state_delta(
        before=_before(MULTI_SIGNAL_UNIVERSE),
        after={k: _snapshot(outcome)[k] for k in MULTI_SIGNAL_UNIVERSE},
        universe=MULTI_SIGNAL_UNIVERSE,
        expected={"outcome.queue_item_count": set_to(count)},
    )


@then(
    "the queue item's ledger chain traces RCA, charter authoring, AT "
    "authoring, RED seal, crafter's GREEN pass, Vera's examine and "
    "commit-slice in order, backed by a commit-slice-verified record"
)
def then_full_chain_traceable(state_04) -> None:
    outcome = state_04["outcome"]
    assert_state_delta(
        before=_before(FULL_CHAIN_UNIVERSE),
        after={k: _snapshot(outcome)[k] for k in FULL_CHAIN_UNIVERSE},
        universe=FULL_CHAIN_UNIVERSE,
        expected={
            "outcome.full_chain_traceable": set_to(True),
            "outcome.slice_commit_verified_present": set_to(True),
        },
    )


@then(
    parsers.parse(
        "sampled at minute {minute:d}, that signal still has exactly one "
        "queue item, not two"
    )
)
def then_no_duplicate_queue_item(intake_fixture, state_04, minute) -> None:
    signal_type, signal_key = state_04["signal"]
    outcome = intake_fixture.sample_for_signal(signal_type, signal_key, minute)
    assert_state_delta(
        before=_before(MULTI_SIGNAL_UNIVERSE),
        after={k: _snapshot(outcome)[k] for k in MULTI_SIGNAL_UNIVERSE},
        universe=MULTI_SIGNAL_UNIVERSE,
        expected={"outcome.queue_item_count": set_to(1)},
    )


@then(
    parsers.parse(
        "sampled at minute {minute:d}, the intake was rejected with a "
        "named reason and no queue item was silently created"
    )
)
def then_intake_rejected_no_silent_queue_item(state_04, minute) -> None:
    outcome = state_04["outcome"]
    assert_state_delta(
        before=_before(REJECTED_UNIVERSE),
        after={k: _snapshot(outcome)[k] for k in REJECTED_UNIVERSE},
        universe=REJECTED_UNIVERSE,
        expected={
            "outcome.intake_rejected": set_to(True),
            "outcome.rejection_reason_named": set_to(True),
            "outcome.queue_item_count": set_to(0),
        },
    )


@then(
    "the CLI surface itself refuses loudly: nonzero exit code, output "
    "naming the unsupported type and the supported set"
)
def then_cli_refuses_loudly(state_04) -> None:
    """EXAMINE fix (Vera FAIL, real-CLI-surface defect): the ledger record
    alone is not enough -- a caller who only watches the CLI's exit code and
    stdout (never reads the ledger) must ALSO observe the rejection loudly,
    self-explaining WHAT was rejected and HOW to fix it (name the supported
    set).
    """
    outcome = state_04["outcome"]
    assert_state_delta(
        before=_before(CLI_SELF_EXPLAINING_UNIVERSE),
        after={k: _snapshot(outcome)[k] for k in CLI_SELF_EXPLAINING_UNIVERSE},
        universe=CLI_SELF_EXPLAINING_UNIVERSE,
        expected={
            "outcome.cli_exit_code": set_to(1),
            "outcome.cli_output_names_unsupported_type": set_to(True),
            "outcome.cli_output_names_supported_set": set_to(True),
        },
    )
