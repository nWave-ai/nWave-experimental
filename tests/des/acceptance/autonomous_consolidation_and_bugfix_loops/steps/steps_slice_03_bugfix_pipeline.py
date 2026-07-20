"""Step bodies for autonomous-consolidation-and-bugfix-loops slice-03
(the bugfix loop drains the defect queue as a pipeline).

Mandate-12 criterion 3: every step body is <=2 statements, ends in a single
`pipeline_fixture.<method>(...)` call (or one assertion), and contains zero
control flow (`if`/`for`/`while`/`try`). All sequencing/arithmetic logic
(the full 7-stage chain walk, the serialized multi-defect box-lane walk)
lives in `BugfixPipelineFixture` (composition_slice_03.py). The typed-
parameter lookup (`STAGE_BY_PHRASE`) is the only dict indexing this file
performs.

Mandate 8: every state-mutating outcome assertion goes through
`assert_state_delta(before, after, universe, expected)` from
`tests.common.state_delta`. The "before" snapshot is the well-defined ZERO
state (`_ZERO_OUTCOME_SNAPSHOT`) -- every scenario starts a FRESH fixture
(fresh tmp_path ledger), so "nothing has fired yet" is provably the baseline
without a separate snapshot-capturing step. Universe entries are port-exposed
observables on `PipelineOutcome` -- never Popen handles, never argv lists,
never the raw ledger path.

Mandate 9 v2: layer 3/4 (real filesystem + real ledger JSONL + real
in-process CLI invocation against tmp_path, @real-io) => example-only. PBT
machinery is intentionally NOT imported (Mandate 11 -- sad paths enumerated
explicitly); density comes from the Scenario Outline `Examples:` table over
the sample-instant axis (AT-15) instead.

Mandate-13: ATs drive through the production `des bugfix-pipeline-tick`
driving port (the real `des.cli.bugfix_pipeline_tick.main` entry) -- NEVER a
direct `from des.domain.bugfix_pipeline import evaluate_and_record`
invocation in test bodies (that seam does not even exist yet -- it is
DELIVER's job).
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from tests.common.state_delta import assert_state_delta, set_to

from .domain_types_slice_03 import STAGE_BY_PHRASE, DefectId


# --- Universe (Mandate 8): port-exposed observables only -------------------

CONCURRENCY_UNIVERSE = frozenset(
    {"outcome.cloud_lane_concurrent_count", "outcome.box_lane_concurrent_count"}
)

BOX_LANE_DEFERRED_UNIVERSE = frozenset(
    {
        "outcome.box_lane_concurrent_count",
        "outcome.box_lane_entry_deferred",
        "outcome.deferred_reason_named",
    }
)

FULL_CHAIN_UNIVERSE = frozenset(
    {"outcome.full_chain_traceable", "outcome.slice_commit_verified_present"}
)

DRAIN_REJECTED_UNIVERSE = frozenset(
    {"outcome.drain_claim_rejected", "outcome.rejection_reason_named"}
)

BOX_LANE_BOUND_UNIVERSE = frozenset(
    {"outcome.box_lane_concurrent_count", "outcome.box_lane_activity_observed"}
)

MID_FAILURE_UNIVERSE = frozenset(
    {"outcome.mid_pipeline_failure_recorded", "outcome.box_lane_freed_after_failure"}
)

# The well-defined ZERO baseline every fresh fixture starts from -- no ticks
# have fired anything yet, so every observable is its own "nothing happened"
# value. Reused as the `before` half of every `assert_state_delta` call
# below (no separate before-snapshot step is needed: the fixture is provably
# fresh at the start of each scenario).
_ZERO_OUTCOME_SNAPSHOT = {
    "outcome.cloud_lane_concurrent_count": 0,
    "outcome.box_lane_concurrent_count": 0,
    "outcome.box_lane_activity_observed": False,
    "outcome.box_lane_entry_deferred": False,
    "outcome.deferred_reason_named": False,
    "outcome.full_chain_traceable": False,
    "outcome.slice_commit_verified_present": False,
    "outcome.drain_claim_rejected": False,
    "outcome.rejection_reason_named": False,
    "outcome.mid_pipeline_failure_recorded": False,
    "outcome.box_lane_freed_after_failure": False,
}


def _snapshot(outcome) -> dict:
    """Universe snapshot of every observable this slice's Thens read. Pure."""
    return {
        "outcome.cloud_lane_concurrent_count": outcome.cloud_lane_concurrent_count,
        "outcome.box_lane_concurrent_count": outcome.box_lane_concurrent_count,
        "outcome.box_lane_activity_observed": outcome.box_lane_activity_observed,
        "outcome.box_lane_entry_deferred": outcome.box_lane_entry_deferred,
        "outcome.deferred_reason_named": outcome.deferred_reason_named,
        "outcome.full_chain_traceable": outcome.full_chain_traceable,
        "outcome.slice_commit_verified_present": (
            outcome.slice_commit_verified_present
        ),
        "outcome.drain_claim_rejected": outcome.drain_claim_rejected,
        "outcome.rejection_reason_named": outcome.rejection_reason_named,
        "outcome.mid_pipeline_failure_recorded": (
            outcome.mid_pipeline_failure_recorded
        ),
        "outcome.box_lane_freed_after_failure": outcome.box_lane_freed_after_failure,
    }


def _before(universe: frozenset) -> dict:
    return {k: _ZERO_OUTCOME_SNAPSHOT[k] for k in universe}


# --- Given -------------------------------------------------------------


@given("a fresh bugfix pipeline")
def given_fresh_pipeline() -> None:
    """No-op narrative precondition -- ``pipeline_fixture`` is already a
    fresh, empty ledger per scenario (fresh ``tmp_path``); this step exists
    for Gherkin readability (Pillar 2 chained narrative), not state setup.
    """


# --- When ----------------------------------------------------------------


@when(parsers.parse('"{defect}" starts {stage_phrase} at minute {minute:d}'))
def when_defect_starts_stage(pipeline_fixture, defect, stage_phrase, minute) -> None:
    pipeline_fixture.start_stage(
        DefectId(defect), STAGE_BY_PHRASE[stage_phrase], minute
    )


@when(
    parsers.parse(
        '"{defect}"\'s {stage_phrase} fails at minute {minute:d} because "{reason}"'
    )
)
def when_defect_stage_fails(
    pipeline_fixture, defect, stage_phrase, minute, reason
) -> None:
    pipeline_fixture.fail_stage(
        DefectId(defect), STAGE_BY_PHRASE[stage_phrase], minute, reason
    )


@when(parsers.parse('someone claims "{defect}" is drained at minute {minute:d}'))
def when_someone_claims_drained(state_03, pipeline_fixture, defect, minute) -> None:
    state_03["outcome"] = pipeline_fixture.claim_drained_and_sample(
        DefectId(defect), minute
    )


@when(
    parsers.parse(
        '"{defect}" walks the full pipeline from RCA to commit-slice starting '
        "at minute {minute:d}"
    )
)
def when_defect_walks_full_chain(state_03, pipeline_fixture, defect, minute) -> None:
    state_03["outcome"] = pipeline_fixture.drive_full_chain(DefectId(defect), minute)


@when(
    parsers.parse(
        '"{d1}", "{d2}" and "{d3}" walk {stage_phrase} one after another starting '
        "at minute {minute:d} with a {gap:d}-minute gap"
    )
)
def when_defects_walk_serialized(
    pipeline_fixture, d1, d2, d3, stage_phrase, minute, gap
) -> None:
    pipeline_fixture.drive_serialized_box_lane_walk(
        [DefectId(d1), DefectId(d2), DefectId(d3)],
        STAGE_BY_PHRASE[stage_phrase],
        minute,
        gap,
    )


# --- Then ------------------------------------------------------------------


@then(
    parsers.parse(
        "sampled at minute {minute:d}, the cloud lane holds at least 2 items "
        "in flight while the box lane holds at most 1"
    )
)
def then_fan_out_bounded(pipeline_fixture, minute) -> None:
    outcome = pipeline_fixture.sample_concurrency_at(minute)
    assert_state_delta(
        before=_before(CONCURRENCY_UNIVERSE),
        after={k: _snapshot(outcome)[k] for k in CONCURRENCY_UNIVERSE},
        universe=CONCURRENCY_UNIVERSE,
        expected={
            "outcome.cloud_lane_concurrent_count": set_to(
                outcome.cloud_lane_concurrent_count
            ),
            "outcome.box_lane_concurrent_count": set_to(
                outcome.box_lane_concurrent_count
            ),
        },
    )
    assert outcome.cloud_lane_concurrent_count >= 2, (
        "D-4 positive (functional): sampled during a multi-defect drain, at "
        "least 2 items must be observed in a cloud-lane stage concurrently. "
        f"Got cloud_lane_concurrent_count={outcome.cloud_lane_concurrent_count}."
    )
    assert outcome.box_lane_concurrent_count <= 1, (
        "D-4 negative (CRITICAL): the box lane must never exceed 1 item in "
        f"flight. Got box_lane_concurrent_count={outcome.box_lane_concurrent_count}."
    )


@then(
    parsers.parse(
        "sampled at minute {minute:d}, the box lane still holds exactly 1 item "
        'and "{defect}"\'s entry was deferred with a named reason'
    )
)
def then_second_entry_deferred(pipeline_fixture, minute, defect) -> None:
    outcome = pipeline_fixture.sample_concurrency_at(minute)
    assert_state_delta(
        before=_before(BOX_LANE_DEFERRED_UNIVERSE),
        after={k: _snapshot(outcome)[k] for k in BOX_LANE_DEFERRED_UNIVERSE},
        universe=BOX_LANE_DEFERRED_UNIVERSE,
        expected={
            "outcome.box_lane_concurrent_count": set_to(1),
            "outcome.box_lane_entry_deferred": set_to(True),
            "outcome.deferred_reason_named": set_to(True),
        },
    )


@then(
    '"defect-7"\'s ledger chain traces RCA, charter authoring, AT authoring, '
    "RED seal, crafter's GREEN pass, Vera's examine and commit-slice in "
    "order, backed by a commit-slice-verified record"
)
def then_full_chain_traceable(state_03) -> None:
    outcome = state_03["outcome"]
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
    '"defect-8"\'s drain claim was rejected for lacking a commit-slice-verified '
    "record, with a named reason"
)
def then_drain_claim_rejected(state_03) -> None:
    outcome = state_03["outcome"]
    assert_state_delta(
        before=_before(DRAIN_REJECTED_UNIVERSE),
        after={k: _snapshot(outcome)[k] for k in DRAIN_REJECTED_UNIVERSE},
        universe=DRAIN_REJECTED_UNIVERSE,
        expected={
            "outcome.drain_claim_rejected": set_to(True),
            "outcome.rejection_reason_named": set_to(True),
        },
    )


@then(
    parsers.parse(
        "sampled at minute {minute:d}, the box lane holds at most 1 item and "
        "box-lane activity was genuinely observed"
    )
)
def then_box_lane_bounded_across_drain(pipeline_fixture, minute) -> None:
    outcome = pipeline_fixture.sample_concurrency_at(minute)
    # Discriminator (Closure Obligations, SILENCE/ABSENCE): a "box lane <= 1"
    # reading is only MEANINGFUL if box-lane activity genuinely happened.
    # Without this check, the RED scaffold (which writes NOTHING at all)
    # would pass this scenario vacuously -- looked-and-genuinely-bounded is
    # not the same as never-actually-looked.
    assert outcome.box_lane_activity_observed, (
        "D-8 discriminator (CRITICAL): this scenario's box-lane-never-"
        "exceeds-1 reading is only meaningful if box-lane activity "
        "genuinely occurred during the drain -- otherwise a scaffold that "
        "writes NOTHING AT ALL would satisfy 'never exceeds 1' vacuously, "
        "the exact false-negative the discriminator mandate forbids. Got "
        f"box_lane_activity_observed={outcome.box_lane_activity_observed}."
    )
    assert_state_delta(
        before=_before(BOX_LANE_BOUND_UNIVERSE),
        after={k: _snapshot(outcome)[k] for k in BOX_LANE_BOUND_UNIVERSE},
        universe=BOX_LANE_BOUND_UNIVERSE,
        expected={
            "outcome.box_lane_concurrent_count": set_to(
                outcome.box_lane_concurrent_count
            ),
            "outcome.box_lane_activity_observed": set_to(True),
        },
    )
    assert outcome.box_lane_concurrent_count <= 1, (
        "D-4/D-8 negative (CRITICAL): the box lane must never show 2+ items "
        "in flight at the same sampled moment, at ANY point during the "
        f"drain. Got box_lane_concurrent_count={outcome.box_lane_concurrent_count} "
        f"at minute {minute}."
    )


@then(
    parsers.parse(
        'sampled at minute {minute:d}, "defect-12"\'s failure was recorded '
        'loudly with a named reason and "defect-13"\'s box-lane entry was '
        "admitted, not deferred"
    )
)
def then_mid_pipeline_failure_frees_slot(pipeline_fixture, minute) -> None:
    outcome = pipeline_fixture.sample_concurrency_at(minute)
    assert_state_delta(
        before=_before(MID_FAILURE_UNIVERSE),
        after={k: _snapshot(outcome)[k] for k in MID_FAILURE_UNIVERSE},
        universe=MID_FAILURE_UNIVERSE,
        expected={
            "outcome.mid_pipeline_failure_recorded": set_to(True),
            "outcome.box_lane_freed_after_failure": set_to(True),
        },
    )
