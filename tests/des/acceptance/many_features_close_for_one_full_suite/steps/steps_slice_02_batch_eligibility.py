"""Step bodies for many-features-close-for-one-full-suite slice-02
(batch-eligibility precheck, realizes D-5).

Mandate-12 criterion 3: step bodies stay small and end in a single
`eligibility_fixture.<method>(...)` call (or a call to one of the module-
level assertion helpers below, mirroring `steps_slice_01_batch_run.py`'s own
`_assert_batch_state`/`_assert_refusal_core_state` pattern) -- the heavy
multi-assertion logic and any comprehension/loop lives in a private
module-level helper, never inside a `@given`/`@when`/`@then`-decorated
function body.

S1 (step-text uniqueness): every literal step string here is DISTINCT from
slice-01's own vocabulary (`steps_slice_01_batch_run.py`). In particular the
`When` step text below is deliberately NOT slice-01's "the maintainer runs
the batch close in-process" -- slice-02 observes RAW json-lines
(`run_batch_and_collect_lines`), never slice-01's typed `BatchRunOutcome`.

Mandate 8: `state_02` carries only port-exposed observables (`exit_code`,
`lines` -- the CLI's own JSON-lines output -- and the pre-declared
`MixedBatchSeed` fields the `Given` step computes) -- never Popen handles or
raw stdout bytes.
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from .domain_types_slice_02 import FAILURE_MODE_BY_TEXT


# --- Given -------------------------------------------------------------------


@given("a shared repository whose whole-tree suite is green")
def given_shared_green_repo(eligibility_fixture) -> None:
    eligibility_fixture.build_shared_repo(genuinely_red=False)


@given(
    parsers.parse("a batch of one ready feature and one feature {failure_description}")
)
def given_mixed_eligibility_batch(
    eligibility_fixture, state_02, failure_description
) -> None:
    mode = FAILURE_MODE_BY_TEXT[failure_description]  # typed dispatch, no raw branch
    state_02["seed"] = eligibility_fixture.seed_mixed_eligibility_batch(mode)


@given("a single feature that is fully attested eligible for the batch")
def given_fully_eligible_batch(eligibility_fixture, state_02) -> None:
    state_02["manifest_path"] = eligibility_fixture.seed_fully_eligible_batch(
        "feature-fully-attested"
    )


# --- When ----------------------------------------------------------------


def _manifest_path_for(state_02: dict) -> str:
    """The ONE manifest path either `Given` step produced -- a negative
    scenario's `MixedBatchSeed.manifest_path`, or the positive scenario's
    own `manifest_path` key. Pure lookup, no branch."""
    return state_02.get("manifest_path") or state_02["seed"].manifest_path


@when("the maintainer runs the batch-eligibility precheck in-process")
def when_run_precheck(eligibility_fixture, state_02) -> None:
    state_02["exit_code"], state_02["lines"] = (
        eligibility_fixture.run_batch_and_collect_lines(_manifest_path_for(state_02))
    )


# --- Then (helpers absorb the multi-assertion / comprehension logic) -------


def _assert_ineligibility_refusal(state_02: dict) -> None:
    seed = state_02["seed"]
    lines = state_02["lines"]
    assert state_02["exit_code"] == 2, (
        "D-5: an ineligible batch member must refuse with a failing exit "
        f"code -- exit_code={state_02['exit_code']!r}, lines={lines!r}"
    )
    assert len(lines) == 1, (
        "GDP-1: the batch-eligibility precheck must refuse BEFORE any gate "
        f"is dispatched -- expected exactly 1 JSON line, got {len(lines)}: "
        f"{lines!r}"
    )
    payload = lines[0]
    assert payload.get("event") == "FeatureEndBatchIneligible", (
        "D-5: the sole line must be a 'FeatureEndBatchIneligible' refusal "
        f"-- got payload={payload!r}"
    )
    assert payload.get("feature_id") == seed.ineligible_feature_id, (
        "GDP-3: the refusal must name the specific ineligible feature by "
        f"id -- expected {seed.ineligible_feature_id!r}, got payload={payload!r}"
    )
    error_text = str(payload.get("error", ""))
    assert seed.ineligible_feature_id in error_text, (
        "GDP-3: the refusal's error text must ALSO name the ineligible "
        f"feature -- error_text={error_text!r}"
    )
    assert any(token in error_text for token in seed.check_substrings), (
        "GDP-3: the refusal must name WHICH check failed (one of "
        f"{seed.check_substrings!r}) -- error_text={error_text!r}"
    )


def _assert_batch_completed(state_02: dict) -> None:
    events = {line.get("event") for line in state_02["lines"]}
    assert state_02["exit_code"] == 0, (
        "a genuinely, attested-eligible member must proceed unaffected -- "
        f"exit_code={state_02['exit_code']!r}, lines={state_02['lines']!r}"
    )
    assert "FeatureEndCycleComplete" in events, (
        f"expected the member's own successful cycle to run -- events={events!r}"
    )
    assert "FeatureEndBatchComplete" in events, (
        f"expected the batch to complete normally -- events={events!r}"
    )


@then("the batch refuses citing the ineligible feature and the failed check")
def then_batch_refuses_citing_check(state_02) -> None:
    _assert_ineligibility_refusal(state_02)


@then("the whole-tree check never ran")
def then_whole_tree_never_ran(eligibility_fixture) -> None:
    assert eligibility_fixture.junit_artifact_count() == 0, (
        "D-5/GDP-1: the expensive whole-tree check must NEVER run when any "
        f"batch member is ineligible -- junit_artifact_count="
        f"{eligibility_fixture.junit_artifact_count()!r}"
    )


@then("neither feature has a closing record")
def then_neither_feature_has_record(eligibility_fixture, state_02) -> None:
    assert eligibility_fixture.feature_end_records_for("feature-ready") == 0, (
        "D-5: NO feature in the batch gets a FeatureEnd record when any "
        "member is ineligible -- the otherwise-ready co-member has records."
    )
    ineligible_id = state_02["seed"].ineligible_feature_id
    assert eligibility_fixture.feature_end_records_for(ineligible_id) == 0, (
        f"D-5: the ineligible feature {ineligible_id!r} must have zero closing records."
    )


@then("the batch completes and the feature has its own closing record")
def then_batch_completes_with_record(eligibility_fixture, state_02) -> None:
    _assert_batch_completed(state_02)
    assert eligibility_fixture.feature_end_records_for("feature-fully-attested") == 2, (
        "the sole, eligible member must still get its own closing record -- "
        f"got {eligibility_fixture.feature_end_records_for('feature-fully-attested')!r}"
    )
