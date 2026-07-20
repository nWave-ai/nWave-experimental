"""Step bodies for many-features-close-for-one-full-suite slice-01
(a maintainer closes several ready features off one shared suite run).

Mandate-12 criterion 3: every step body is <=2 statements, ends in a single
`batch_fixture.<method>(...)` call (or one assertion), and contains zero
control flow (`if`/`for`/`while`/`try`). All business logic lives in
`BatchFixture` (composition_slice_01.py). The typed-parameter lookup
(`PHRASE_BY_TEXT`) is the single dict indexing this file performs.

Mandate 8: the state-mutating outcome assertion goes through
`assert_state_delta(before, after, universe, expected)` from
`tests.common.state_delta`. Universe entries are port-exposed observables on
`BatchRunOutcome` -- never Popen handles, never raw stdout bytes, never
adapter internals. Every scenario's primary `Then` declares EVERY key of its
OWN declared universe in ONE combined call (mirrors the
`parallel-work-cleans-up-after-merge-back` slice-01 bugfix: a partial
declaration against a broad shared universe never discriminates
correct-vs-incorrect behaviour). Two universes exist: `BATCH_UNIVERSE` (the
full 7-field observable, used by scenarios whose `Then` step-text is NOT
reused elsewhere) and `REFUSAL_CORE_UNIVERSE` (the 5 fields IDENTICAL across
the two refusal scenarios that share the "the batch refuses with a failing
exit code" step-text) -- `batch_event`/`junit_artifact_count`, which
genuinely differ between a red-suite refusal and a malformed-manifest
refusal, are verified by each scenario's OWN scenario-specific secondary
`Then` instead (see the module comment above `REFUSAL_CORE_UNIVERSE`).

The batch-of-one equivalence scenario (AT-BATCH-4) is a byte-for-byte
COMPARISON between two independent invocations (the classic close vs. the
batch entry point), not a single outcome's before/after delta -- it uses a
plain structural equality assertion instead, mirroring the worktree-cleanup
precedent's own secondary plain-assert style for detail fields.

Mandate 9 v2: layer 3 (a hermetic tmp_path git-free pytest repo + one real
subprocess fork for the walking skeleton, @real-io) => example-only. PBT
machinery is intentionally NOT imported (Mandate 11 -- sad paths enumerated
explicitly).

Mandate-13: ATs drive through the production `des` driving surface (the
`des.cli.__main__` dispatcher in-process, or the real installed `des`
console-script for the walking skeleton) -- NEVER a direct import of the
not-yet-existing batch service module in test bodies.
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from tests.common.state_delta import assert_state_delta, set_to

from .domain_types_slice_01 import PHRASE_BY_TEXT


# --- Universe (Mandate 8): port-exposed observables only --------------------

BATCH_UNIVERSE = frozenset(
    {
        "outcome.exit_code",
        "outcome.batch_event",
        "outcome.member_count",
        "outcome.member_success_count",
        "outcome.member_refused_count",
        "outcome.junit_artifact_count",
        "outcome.total_feature_end_records",
    }
)

# The literal "the batch refuses with a failing exit code" step-text is
# REUSED across two scenarios (AT-BATCH-2 red-suite vs. AT-BATCH-3 malformed-
# manifest, Pillar 2) whose `batch_event` and `junit_artifact_count` genuinely
# DIFFER (a red suite still ran the check once; a malformed manifest never
# dispatches it at all) -- so the SHARED primary delta below declares only
# the fields IDENTICAL across both refusal shapes. `batch_event` and
# `junit_artifact_count` are verified by each scenario's OWN scenario-specific
# secondary Then (never guessed/branched inside a step body -- zero control
# flow, Mandate-12 criterion 3).
REFUSAL_CORE_UNIVERSE = frozenset(
    {
        "outcome.exit_code",
        "outcome.member_count",
        "outcome.member_success_count",
        "outcome.member_refused_count",
        "outcome.total_feature_end_records",
    }
)


def _batch_snapshot(state: dict) -> dict:
    """Universe snapshot of the batch observables. Pure function.

    Returns `None` sentinels for unobserved keys so the before-snapshot is
    well-defined before the batch run fires.
    """
    outcome = state.get("outcome")
    return {
        "outcome.exit_code": getattr(outcome, "exit_code", None),
        "outcome.batch_event": getattr(outcome, "batch_event", None),
        "outcome.member_count": getattr(outcome, "member_count", None),
        "outcome.member_success_count": getattr(outcome, "member_success_count", None),
        "outcome.member_refused_count": getattr(outcome, "member_refused_count", None),
        "outcome.junit_artifact_count": getattr(outcome, "junit_artifact_count", None),
        "outcome.total_feature_end_records": getattr(
            outcome, "total_feature_end_records", None
        ),
    }


def _assert_batch_state(state: dict, **expected_values) -> None:
    """The ONE combined `assert_state_delta` call every scenario's primary
    `Then` uses -- declares EVERY `BATCH_UNIVERSE` key explicitly."""
    after = _batch_snapshot(state)
    assert_state_delta(
        before={k: state["before"][k] for k in BATCH_UNIVERSE},
        after={k: after[k] for k in BATCH_UNIVERSE},
        universe=BATCH_UNIVERSE,
        expected={
            f"outcome.{name}": set_to(value) for name, value in expected_values.items()
        },
    )


def _assert_refusal_core_state(state: dict, **expected_values) -> None:
    """The SHARED-step combined delta over `REFUSAL_CORE_UNIVERSE` only --
    see the module-level comment on `REFUSAL_CORE_UNIVERSE` for why
    `batch_event`/`junit_artifact_count` are excluded here."""
    after = _batch_snapshot(state)
    assert_state_delta(
        before={k: state["before"][k] for k in REFUSAL_CORE_UNIVERSE},
        after={k: after[k] for k in REFUSAL_CORE_UNIVERSE},
        universe=REFUSAL_CORE_UNIVERSE,
        expected={
            f"outcome.{name}": set_to(value) for name, value in expected_values.items()
        },
    )


# --- Given -------------------------------------------------------------------


@given(
    parsers.parse(
        "two ready features sharing one repository whose whole-tree suite is {suite_state}"
    )
)
def given_two_ready_features(batch_fixture, state_01, suite_state) -> None:
    phrase = PHRASE_BY_TEXT[suite_state]  # typed-parameter validation, no raw dispatch
    batch_fixture.build_shared_repo(genuinely_red=phrase.value == "genuinely red")
    batch_fixture.seed_ready_feature("feature-alpha")
    batch_fixture.seed_ready_feature("feature-beta")


@given("a manifest naming both features for one batch run")
def given_manifest_both_features(batch_fixture, state_01) -> None:
    state_01["manifest_path"] = batch_fixture.write_manifest_for(
        ["feature-alpha", "feature-beta"]
    )


@given("a manifest where one entry is missing a required field")
def given_manifest_malformed(batch_fixture, state_01) -> None:
    state_01["manifest_path"] = batch_fixture.write_malformed_manifest(
        ["feature-alpha", "feature-beta"]
    )


@given("a single ready feature the maintainer already knows how to close alone")
def given_single_ready_feature(batch_fixture, state_01) -> None:
    batch_fixture.build_shared_repo(genuinely_red=False)
    state_01["feature_id"] = "feature-solo"
    state_01["feature_dir"] = batch_fixture.seed_ready_feature("feature-solo")


@given("a batch of one ready feature and one eligible feature whose own leg refuses")
def given_mixed_batch(batch_fixture, state_01) -> None:
    # R5-vs-R6 reconciliation: the member's OWN leg refuses for a
    # NON-eligibility reason (D-D6) -- it passes every D-5 eligibility
    # check, so a future precheck lets the batch proceed to per-member
    # cycles, unlike an undelivered-slice (eligibility) trigger.
    batch_fixture.build_shared_repo(genuinely_red=False)
    batch_fixture.seed_ready_feature("feature-ready")
    batch_fixture.seed_eligible_but_leg_failing_feature("feature-not-ready")
    state_01["manifest_path"] = batch_fixture.write_manifest_for(
        ["feature-ready", "feature-not-ready"]
    )


# --- When ---------------------------------------------------------------


@when(
    "the maintainer runs the batch close against the real installed des console-script"
)
def when_run_batch_subprocess(batch_fixture, state_01) -> None:
    state_01["before"] = _batch_snapshot(state_01)
    state_01["outcome"] = batch_fixture.run_batch_subprocess(state_01["manifest_path"])


@when("the maintainer runs the batch close in-process")
def when_run_batch_in_process(batch_fixture, state_01) -> None:
    state_01["before"] = _batch_snapshot(state_01)
    state_01["outcome"] = batch_fixture.run_batch_in_process(state_01["manifest_path"])


@when(
    "the maintainer closes it the classic way, and again through the batch entry point "
    "as a batch of one"
)
def when_classic_then_batch_of_one(batch_fixture, state_01) -> None:
    state_01["classic"] = batch_fixture.run_classic(
        state_01["feature_id"], state_01["feature_dir"]
    )
    state_01["batch_of_one"] = batch_fixture.run_batch_of_one(
        state_01["feature_id"], state_01["feature_dir"]
    )


# --- Then (primary -- ONE combined assert_state_delta per scenario) --------


@then("the whole-tree check produced exactly one shared suite artifact")
def then_one_shared_suite_artifact(state_01) -> None:
    _assert_batch_state(
        state_01,
        exit_code=0,
        batch_event="FeatureEndBatchComplete",
        member_count=2,
        member_success_count=2,
        member_refused_count=0,
        junit_artifact_count=1,
        total_feature_end_records=4,
    )


@then("the batch refuses with a failing exit code")
def then_batch_refuses(state_01) -> None:
    _assert_refusal_core_state(
        state_01,
        exit_code=2,
        member_count=0,
        member_success_count=0,
        member_refused_count=0,
        total_feature_end_records=0,
    )


@then("the whole-tree check still produced exactly one shared suite artifact")
def then_shared_artifact_still_once(state_01) -> None:
    _assert_batch_state(
        state_01,
        exit_code=2,
        batch_event="FeatureEndBatchComplete",
        member_count=2,
        member_success_count=1,
        member_refused_count=1,
        junit_artifact_count=1,
        total_feature_end_records=2,
    )


# --- Then/And (secondary -- PLAIN attribute asserts, never a 2nd state_delta
# call reusing BATCH_UNIVERSE with a partial declaration) -------------------


@then("each of the two features has its own closing record")
def then_each_feature_has_own_record(batch_fixture) -> None:
    assert batch_fixture.feature_end_records_for("feature-alpha") == 2, (
        "D-3: each feature must emit its OWN closing record off the shared "
        f"suite result -- got {batch_fixture.feature_end_records_for('feature-alpha')!r}."
    )
    assert batch_fixture.feature_end_records_for("feature-beta") == 2, (
        "D-3: each feature must emit its OWN closing record off the shared "
        f"suite result -- got {batch_fixture.feature_end_records_for('feature-beta')!r}."
    )


@then("the refusal names the failing tests")
def then_refusal_names_failing_tests(state_01) -> None:
    outcome = state_01["outcome"]
    assert outcome.batch_event == "FeatureEndBatchRefused", (
        "D-4: a red shared suite must emit ONE batch-level "
        f"FeatureEndBatchRefused -- got batch_event={outcome.batch_event!r}."
    )
    assert outcome.junit_artifact_count == 1, (
        "D-3: the shared full-suite check must still have RUN (once) even "
        f"though it went red -- got junit_artifact_count={outcome.junit_artifact_count!r}."
    )
    assert outcome.failing_tests_named, (
        "GDP-3/D-4: a red shared-suite batch refusal must name the failing "
        f"tests -- got failing_tests_named={outcome.failing_tests_named!r}."
    )


@then("neither feature has a closing record")
def then_neither_feature_has_record(state_01) -> None:
    outcome = state_01["outcome"]
    assert outcome.total_feature_end_records == 0, (
        "D-4: a red shared suite must refuse the WHOLE batch -- zero closing "
        f"records for any feature. got total_feature_end_records="
        f"{outcome.total_feature_end_records!r}."
    )


@then("the whole-tree check never ran")
def then_whole_tree_check_never_ran(state_01) -> None:
    outcome = state_01["outcome"]
    assert outcome.batch_event == "FeatureEndBatchManifestRefused", (
        "GDP-1: a structurally malformed manifest must emit ONE batch-level "
        f"FeatureEndBatchManifestRefused -- got batch_event={outcome.batch_event!r}."
    )
    assert outcome.junit_artifact_count == 0, (
        "GDP-1: a structurally malformed manifest must refuse before ANY "
        f"gate is dispatched -- got junit_artifact_count={outcome.junit_artifact_count!r}."
    )


@then("the refusal names the malformed entry")
def then_refusal_names_malformed_entry(state_01) -> None:
    outcome = state_01["outcome"]
    assert "reviewer_agent_id" in outcome.refusal_error_text, (
        "the manifest refusal must name the MISSING field -- got "
        f"refusal_error_text={outcome.refusal_error_text!r}."
    )
    assert "feature-beta" in outcome.refusal_error_text, (
        "the manifest refusal must name the malformed entry's feature -- got "
        f"refusal_error_text={outcome.refusal_error_text!r}."
    )


@then("the ready feature still has its own closing record")
def then_ready_feature_has_own_record(batch_fixture) -> None:
    assert batch_fixture.feature_end_records_for("feature-ready") == 2, (
        "D-D6: a batch-mate's own successful close must be unaffected by the "
        f"OTHER member's refusal -- got "
        f"{batch_fixture.feature_end_records_for('feature-ready')!r} records."
    )


@then("the not-ready feature has no closing record of its own")
def then_not_ready_feature_has_no_record(batch_fixture) -> None:
    assert batch_fixture.feature_end_records_for("feature-not-ready") == 0, (
        "D-D6: a refused member must never leave a closing record -- got "
        f"{batch_fixture.feature_end_records_for('feature-not-ready')!r} records."
    )


@then(
    "the batch entry point's own record for that feature matches the classic close exactly"
)
def then_batch_of_one_matches_classic(state_01) -> None:
    classic, batch_of_one = state_01["classic"], state_01["batch_of_one"]
    assert classic.get("event") == "FeatureEndCycleComplete", (
        "fixture precondition: the classic close must genuinely succeed -- "
        f"got classic={classic!r}."
    )
    classic_shape = (
        classic.get("event"),
        classic.get("feature_id"),
        classic.get("verdict_hash"),
    )
    batch_shape = (
        batch_of_one.get("event"),
        batch_of_one.get("feature_id"),
        batch_of_one.get("verdict_hash"),
    )
    assert classic_shape == batch_shape, (
        "D-1: a batch of exactly one feature must be byte-identical to the "
        f"classic close -- classic={classic_shape!r}, batch-of-one={batch_shape!r}."
    )
