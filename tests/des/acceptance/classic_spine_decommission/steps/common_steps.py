"""Shared step vocabulary for the classic-spine-decommission acceptance suite.

Mandate-12 (SSOT via Types + Services + DSL): the seven slice `.feature` files
share ONE step vocabulary. Each decorator below is a parameterized template
over a typed-enum parameter (from `domain_types.py`) -- the DSL emerges from
the typed domain concepts, not from one decorator per literal phrase.

Mandate-12 criterion 3: every step body is <=2 statements, ends in a single
`composition.<service>(...)` call (or one assertion delegating to a service
observable), and contains no control flow. Business logic lives in
`composition.py` service methods, never here.

The slice `test_slice_NN_*.py` files import `*` from this module and call
`scenarios(...)` on their own `.feature` file -- pytest-bdd resolves the steps
from this shared module. New step decorators introduced only in one slice file
are a smell (Mandate 10 shared-vocabulary contract).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when

from tests.common.state_delta import assert_state_delta, set_to, unchanged

from .composition import (
    ConversionComposition,
    DeprecationComposition,
    FeatureScanComposition,
    LedgerInterleaveComposition,
    ReplayComposition,
)
from .domain_types import (
    CONVERSION_OUTCOME_BY_PHRASE,
    CORRUPTION_BY_PHRASE,
    FEATURE_CLASS_BY_PHRASE,
    INTERRUPT_BY_PHRASE,
    SHA_VERDICT_BY_PHRASE,
    SLICE_STATUS_BY_PHRASE,
    WORKFLOW_MODE_BY_PHRASE,
    AdvisoryState,
    FeatureClass,
    FeatureId,
    LedgerReadOutcome,
    LedgerWriter,
    ReplayOutcome,
)


# --- Fixtures ----------------------------------------------------------------


@pytest.fixture
def scan(tmp_path: Path) -> FeatureScanComposition:
    """Production-wired `des-classify-features` over a tmp_path feature tree."""
    return FeatureScanComposition(workspace=tmp_path / "ws")


@pytest.fixture
def ledger(tmp_path: Path) -> LedgerInterleaveComposition:
    """Production-wired F-13 multi-writer ledger interleave composition."""
    return LedgerInterleaveComposition(deliver_dir=tmp_path / "deliver")


@pytest.fixture
def convert(tmp_path: Path) -> ConversionComposition:
    """Production-wired `des-convert-to-atdd-pure` over a tmp_path workspace."""
    return ConversionComposition(workspace=tmp_path / "ws")


@pytest.fixture
def replay(tmp_path: Path) -> ReplayComposition:
    """Composition root for the M5 audit-log replay verification gate."""
    return ReplayComposition(workspace=tmp_path / "ws")


@pytest.fixture
def deprecation(tmp_path: Path) -> DeprecationComposition:
    """Production-wired classic-deprecation marking composition (slice-07)."""
    return DeprecationComposition(workspace=tmp_path / "ws")


@pytest.fixture
def box() -> dict[str, object]:
    """Carrier for results + pre-action universe snapshots across G/W/T steps."""
    return {}


# --- Given: detection -- feature dirs of each class --------------------------


@given(parsers.parse('the legacy feature "{feature_id}" is {feature_class}'))
def given_legacy_feature(
    scan: FeatureScanComposition, feature_id: str, feature_class: str
) -> None:
    scan.create_feature_dir(
        FeatureId(feature_id), FEATURE_CLASS_BY_PHRASE[feature_class]
    )


@given(parsers.parse('the feature "{feature_id}" has {corruption}'))
def given_corrupt_feature(
    scan: FeatureScanComposition, feature_id: str, corruption: str
) -> None:
    scan.corrupt_feature_artifacts(
        FeatureId(feature_id), CORRUPTION_BY_PHRASE[corruption]
    )


@given(
    parsers.parse('the feature "{feature_id}" carries both a roadmap and a slice plan')
)
def given_feature_both_artifacts(scan: FeatureScanComposition, feature_id: str) -> None:
    scan.give_feature_both_roadmap_and_slice_plan(FeatureId(feature_id))


# --- Given: conversion -- a classic feature awaiting conversion --------------


@given(
    parsers.parse(
        'a classic feature "{feature_id}" that {plan_phrase} a recovered slice plan'
    )
)
def given_classic_feature(
    convert: ConversionComposition, feature_id: str, plan_phrase: str
) -> None:
    convert.create_classic_feature(
        FeatureId(feature_id),
        FeatureClass.CLASSIC_MID_IMPLEMENTATION,
        has_slice_plan=(plan_phrase == "carries"),
    )


@given(parsers.parse("the classic feature has {count:d} roadmap steps"))
def given_roadmap_step_count(convert: ConversionComposition, count: int) -> None:
    convert.set_roadmap_steps(count)


@given(parsers.parse('roadmap steps "{step_ids}" constitute slice "{slice_id}"'))
def given_steps_constitute_slice(
    convert: ConversionComposition, step_ids: str, slice_id: str
) -> None:
    convert.map_steps_to_slice(tuple(step_ids.split()), slice_id)


@given(
    parsers.parse(
        'step "{step_id}" was committed at "{sha}" whose commit {sha_verdict}'
    )
)
def given_step_committed(
    convert: ConversionComposition, step_id: str, sha: str, sha_verdict: str
) -> None:
    convert.commit_step_with_sha_verdict(
        step_id, sha, SHA_VERDICT_BY_PHRASE[sha_verdict]
    )


@given(
    parsers.parse('step "{step_id}" appears committed twice at the same commit "{sha}"')
)
def given_step_committed_twice(
    convert: ConversionComposition, step_id: str, sha: str
) -> None:
    convert.log_step_committed_twice(step_id, sha)


@given("the feature's acceptance scenarios carry no slice tags")
def given_scenarios_untagged(convert: ConversionComposition) -> None:
    convert.leave_scenarios_untagged()


@given(parsers.parse("the conversion is interrupted {interrupt_phrase}"))
def given_conversion_interrupted(
    convert: ConversionComposition, interrupt_phrase: str
) -> None:
    convert.arm_interrupt(INTERRUPT_BY_PHRASE[interrupt_phrase])


@given("the architect has classified the feature with the real classifier")
def given_classified_with_real_classifier(convert: ConversionComposition) -> None:
    convert.classify_with_real_classifier()


@given("the feature directory changes after the real classification")
def given_feature_dir_advances_after_real_classification(
    convert: ConversionComposition,
) -> None:
    convert.advance_feature_dir_after_real_classification()


@given("the feature directory is not writable")
def given_feature_dir_read_only(convert: ConversionComposition) -> None:
    convert.make_feature_dir_read_only()


# --- Given: F-13 multi-writer ledger -----------------------------------------


@given(parsers.parse('an installed feature "{feature_id}" with a shared ledger'))
def given_installed_feature(
    ledger: LedgerInterleaveComposition, feature_id: str
) -> None:
    ledger.create_installed_feature(FeatureId(feature_id))


@given(
    parsers.parse(
        'the review verdict writer appends a verdict record for slice "{slice_id}"'
    )
)
def given_verdict_writer_appends(
    ledger: LedgerInterleaveComposition, slice_id: str
) -> None:
    ledger.writer_appends_record(LedgerWriter.AT_REVIEW_VERDICT, slice_id)


@given(
    parsers.parse(
        'the completion-ledger writer appends a gate event for slice "{slice_id}"'
    )
)
def given_completion_writer_appends(
    ledger: LedgerInterleaveComposition, slice_id: str
) -> None:
    ledger.writer_appends_record(LedgerWriter.AT_COMPLETION, slice_id)


# --- Given: deprecation ------------------------------------------------------


@given(parsers.parse("a project configured for {workflow_mode}"))
def given_project_workflow_mode(
    deprecation: DeprecationComposition, workflow_mode: str
) -> None:
    deprecation.configure_workflow_mode(WORKFLOW_MODE_BY_PHRASE[workflow_mode])


@given("a commit predating the classic-spine decommission")
def given_pre_decommission_commit(replay: ReplayComposition) -> None:
    replay.given_pre_decommission_commit()


# --- When: snapshot universe then run the driving port -----------------------


@when("the architect classifies the feature tree")
def when_classify(scan: FeatureScanComposition, box: dict[str, object]) -> None:
    box["before"] = scan.capture_universe()
    box["exit_code"] = scan.run_classify_features()


@when("the architect previews the conversion")
def when_dry_run(convert: ConversionComposition, box: dict[str, object]) -> None:
    box["before"] = convert.capture_universe()
    box["plan"] = convert.run_dry_run()


@when("the architect converts the feature")
def when_convert(convert: ConversionComposition, box: dict[str, object]) -> None:
    box["before"] = convert.capture_universe()
    box["result"] = convert.run_convert()


@when("the architect converts the feature a second time")
def when_convert_again(convert: ConversionComposition, box: dict[str, object]) -> None:
    box["journal_before"] = convert.journal_records()
    box["result"] = convert.run_convert_again()


@when("the architect rolls back the conversion")
def when_rollback(convert: ConversionComposition, box: dict[str, object]) -> None:
    box["result"] = convert.run_rollback()


@when(parsers.parse('the architect drains the features "{feature_ids}"'))
def when_drain(
    convert: ConversionComposition, box: dict[str, object], feature_ids: str
) -> None:
    box["result"] = convert.run_drain(
        tuple(FeatureId(fid) for fid in feature_ids.split())
    )


@when("the carpaccio order read consumes the shared ledger")
def when_order_read(
    ledger: LedgerInterleaveComposition, box: dict[str, object]
) -> None:
    box["read"] = ledger.run_carpaccio_order_read()


@when("an atdd_pure dispatch runs against the installed feature")
def when_installed_dispatch(
    ledger: LedgerInterleaveComposition, box: dict[str, object]
) -> None:
    box["exit_code"] = ledger.run_atdd_pure_dispatch_installed()


@when("a DELIVER dispatch runs")
def when_dispatch(deprecation: DeprecationComposition, box: dict[str, object]) -> None:
    box["before"] = deprecation.capture_universe()
    box["exit_code"] = deprecation.run_dispatch()


@when("the legacy commit is replayed")
def when_replay(replay: ReplayComposition, box: dict[str, object]) -> None:
    box["replay"] = replay.run_replay()


# --- Then: classification observables ----------------------------------------


@then(parsers.parse('the manifest classifies "{feature_id}" as {feature_class}'))
def then_manifest_class(
    scan: FeatureScanComposition, feature_id: str, feature_class: str
) -> None:
    rows = {r.feature_id: r.feature_class for r in scan.manifest_rows()}
    assert rows[FeatureId(feature_id)] == FEATURE_CLASS_BY_PHRASE[feature_class]


@then(parsers.parse('the manifest records "{feature_id}" as having a slice plan'))
def then_manifest_has_slice_plan(scan: FeatureScanComposition, feature_id: str) -> None:
    rows = {r.feature_id: r.has_slice_plan for r in scan.manifest_rows()}
    assert rows[FeatureId(feature_id)] is True


@then("the classifier did not crash")
def then_no_crash(scan: FeatureScanComposition) -> None:
    assert scan.classifier_crashed() is False


@then("the developer repository is left untouched by the classification")
def then_classify_repo_untouched(
    scan: FeatureScanComposition, box: dict[str, object]
) -> None:
    after = scan.capture_universe()
    assert_state_delta(
        before=box["before"],
        after=after,
        universe={
            "git.status_porcelain",
            "git.head_sha",
            "manifest.exists",
            "manifest.row_count",
        },
        expected={
            "git.status_porcelain": unchanged(),
            "git.head_sha": unchanged(),
            "manifest.exists": set_to(True),
            # AT defect fix (DELIVER 01-01): the universe declares
            # `manifest.row_count` but the original `expected` omitted its
            # predicate. Classification legitimately writes one row, so under
            # strict=True the 0->1 transition was an undeclared_change. The
            # scenario's intent ("the manifest classifies legacy-alpha") IS a
            # one-row manifest -- set_to(1) completes the universe declaration
            # and strengthens the assertion. Flagged to nw-acceptance-designer.
            "manifest.row_count": set_to(1),
        },
        strict=True,
    )


# --- Then: conversion observables --------------------------------------------


@then(parsers.parse("the conversion is {conversion_outcome}"))
def then_conversion_outcome(box: dict[str, object], conversion_outcome: str) -> None:
    result = box["result"]
    assert result.outcome == CONVERSION_OUTCOME_BY_PHRASE[conversion_outcome]


@then(parsers.parse("the preview reports the conversion would be {conversion_outcome}"))
def then_preview_outcome(box: dict[str, object], conversion_outcome: str) -> None:
    plan = box["plan"]
    assert plan.blocker == CONVERSION_OUTCOME_BY_PHRASE.get(conversion_outcome)


@then(parsers.parse('slice "{slice_id}" is reconciled as {slice_status}'))
def then_slice_status(
    convert: ConversionComposition, slice_id: str, slice_status: str
) -> None:
    assert convert.slice_status(slice_id) == SLICE_STATUS_BY_PHRASE[slice_status]


@then(
    parsers.parse(
        'slice "{slice_id}" records the committed work as provenance "{shas}"'
    )
)
def then_slice_provenance(
    convert: ConversionComposition, slice_id: str, shas: str
) -> None:
    assert convert.slice_provenance(slice_id) == tuple(shas.split())


@then("the feature now runs on the atdd_pure spine")
def then_feature_on_atdd_pure(convert: ConversionComposition) -> None:
    assert convert.effective_workflow_mode().value == "atdd_pure"


@then("the seeded ledger records carry sequence numbers and hashes")
def then_ledger_seeded_via_api(convert: ConversionComposition) -> None:
    assert convert.ledger_seeded_via_m7_api() is True


@then("the preview writes nothing to the feature directory")
def then_preview_writes_nothing(
    convert: ConversionComposition, box: dict[str, object]
) -> None:
    after = convert.capture_universe()
    assert_state_delta(
        before=box.get("before", after),
        after=after,
        universe={
            "feature.slice_plan_heading_present",
            "feature.workflow_mode",
            "feature.ledger_record_count",
            "feature.roadmap_archived",
        },
        expected={
            "feature.slice_plan_heading_present": unchanged(),
            "feature.workflow_mode": unchanged(),
            "feature.ledger_record_count": unchanged(),
            "feature.roadmap_archived": unchanged(),
        },
        strict=True,
    )


@then("the feature is never left half-converted")
def then_no_half_conversion(convert: ConversionComposition) -> None:
    assert convert.feature_is_half_converted() is False


@then("the conversion journal is unchanged by the second run")
def then_journal_idempotent(
    convert: ConversionComposition, box: dict[str, object]
) -> None:
    assert convert.journal_records() == box["journal_before"]


@then("the pre-conversion classic artifacts are restored")
def then_rollback_restores(convert: ConversionComposition) -> None:
    assert convert.classic_artifacts_present() is True and (
        convert.roadmap_archived() is False
    )


@then(parsers.parse('the features "{feature_ids}" are parked for follow-up'))
def then_features_parked(convert: ConversionComposition, feature_ids: str) -> None:
    assert convert.parked_features() == tuple(
        FeatureId(fid) for fid in feature_ids.split()
    )


@then(parsers.parse('the features "{feature_ids}" are converted'))
def then_features_converted(convert: ConversionComposition, feature_ids: str) -> None:
    assert convert.converted_features() == tuple(
        FeatureId(fid) for fid in feature_ids.split()
    )


@then("the classic roadmap artifacts are archived under the feature")
def then_roadmap_archived(convert: ConversionComposition) -> None:
    assert convert.roadmap_archived() is True


@then("the classic roadmap artifacts are not archived under the feature")
def then_roadmap_not_archived(convert: ConversionComposition) -> None:
    assert convert.roadmap_archived() is False


@then("the converted feature passes the carpaccio entry gate dry-run")
def then_carpaccio_dry_run_passes(convert: ConversionComposition) -> None:
    assert convert.carpaccio_gate_dry_run_passes() is True


# --- Then: F-13 ledger observables -------------------------------------------


@then("the carpaccio order read accepts the mixed-writer ledger")
def then_order_read_accepts(box: dict[str, object]) -> None:
    read = box["read"]
    assert read.read_outcome == LedgerReadOutcome.ACCEPTED


@then("no ledger integrity violation is raised")
def then_no_integrity_violation(box: dict[str, object]) -> None:
    read = box["read"]
    assert read.read_outcome != LedgerReadOutcome.INTEGRITY_RAISED


@then("the installed atdd_pure dispatch completes successfully")
def then_installed_dispatch_ok(box: dict[str, object]) -> None:
    assert box["exit_code"] == 0


# --- Then: deprecation observables -------------------------------------------


@then(parsers.parse("the dispatch resolves to {workflow_mode}"))
def then_resolved_mode(deprecation: DeprecationComposition, workflow_mode: str) -> None:
    assert deprecation.resolved_mode() == WORKFLOW_MODE_BY_PHRASE[workflow_mode]


@then("a classic-spine deprecation advisory is emitted")
def then_advisory_fired(deprecation: DeprecationComposition) -> None:
    assert deprecation.advisory_state() == AdvisoryState.FIRED


@then("no classic-spine deprecation advisory is emitted")
def then_advisory_not_fired(deprecation: DeprecationComposition) -> None:
    assert deprecation.advisory_state() == AdvisoryState.NOT_FIRED


@then("the dispatch refuses removed classic with migration required")
def then_classic_removed(deprecation: DeprecationComposition) -> None:
    payload = deprecation.removal_payload()
    assert payload["outcome"] == "CLASSIC_MODE_REMOVED"
    assert payload["reason_code"] == "MIGRATION_REQUIRED"
    assert payload["effective_mode"] is None


@then("the dispatch refuses the undeclared mode without defaulting")
def then_mode_undeclared(deprecation: DeprecationComposition) -> None:
    """An undeclared mode is its OWN refusal, not the classic one.

    Two different causes with two different remedies: a project carrying the
    retired selector must migrate; a project that declares nothing must declare.
    Collapsing them would tell an operator to migrate away from something they
    never chose -- the same conflation filed today against the PreToolUse path.
    """
    payload = deprecation.removal_payload()
    assert payload["outcome"] == "MODE_UNDECLARED", payload
    assert payload["effective_mode"] is None, payload


@then("the classic dispatch still runs to completion as a fallback")
def then_classic_fallback_works(deprecation: DeprecationComposition) -> None:
    assert deprecation.classic_dispatch_completed() is True


@then("a customer migration note is shipped")
def then_migration_note_shipped(deprecation: DeprecationComposition) -> None:
    assert deprecation.migration_note_present() is True


@then(parsers.parse('the classic artifact "{artifact}" is still present'))
def then_classic_artifact_present(
    deprecation: DeprecationComposition, artifact: str
) -> None:
    assert deprecation.classic_artifact_deleted(artifact) is False


# --- Then: replay observable -------------------------------------------------


@then("the audit-log replay runs green")
def then_replay_green(box: dict[str, object]) -> None:
    assert box["replay"] == ReplayOutcome.GREEN
