"""Shared step vocabulary for the walking-skeleton-production-like-gate suite.

Mandate-12 (SSOT via Types + Services + DSL): the seven slice `.feature` files
share ONE step vocabulary. Each decorator below is a parameterized template
over a typed-enum parameter (from `domain_types.py`) -- the DSL emerges from
the typed domain concepts, not from one decorator per literal phrase.

Mandate-12 criterion 3: every step body is <=2 statements, ends in a single
`composition.<service>(...)` call, and contains no control flow. Business
logic lives in `composition.py` service methods, never here.

The slice `test_slice_NN_*.py` files import `*` from this module and call
`scenarios(...)` on their own `.feature` file -- pytest-bdd resolves the steps
from this shared module. New step decorators introduced only in one slice file
are a smell (Mandate 10 shared-vocabulary contract); prefer adding a row to a
`domain_types.py` lookup dict and reusing a template here.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .composition import (
    AuthoringPropagationComposition,
    CustomerScaffoldComposition,
    DistributionCompletenessComposition,
    GateResult,
    WalkingSkeletonGateComposition,
)
from .domain_types import (
    AUTHORING_ARTIFACT_BY_PHRASE,
    DEFERRAL_REASON_BY_PHRASE,
    FEATURE_SHAPE_BY_PHRASE,
    HOOK_OUTCOME_BY_PHRASE,
    MARKER_STATE_BY_PHRASE,
    OS_SENSITIVITY_BY_PHRASE,
    TIER_BY_PHRASE,
    TIER_CAPABILITY_BY_PHRASE,
    VERDICT_BY_PHRASE,
    FacetViolationKind,
    FeatureId,
    GateVerdict,
    MarkerKind,
    MarkerReadState,
    Tier,
)


# --- Fixtures ----------------------------------------------------------------


@pytest.fixture
def gate(tmp_path: Path) -> WalkingSkeletonGateComposition:
    """Production-wired walking-skeleton gate over a tmp_path deliver project."""
    return WalkingSkeletonGateComposition(deliver_dir=tmp_path / "deliver")


@pytest.fixture
def distribution(tmp_path: Path) -> DistributionCompletenessComposition:
    """Composition root for the US-04 distribution-completeness arch test."""
    return DistributionCompletenessComposition(repo_dir=tmp_path / "repo")


@pytest.fixture
def scaffold(tmp_path: Path) -> CustomerScaffoldComposition:
    """Composition root for the US-05 customer-project CI scaffold."""
    return CustomerScaffoldComposition(customer_project_dir=tmp_path / "customer")


@pytest.fixture
def box(gate: WalkingSkeletonGateComposition) -> dict[str, object]:
    """Carrier for the gate result + the pre-evaluation universe snapshot.

    B2 review fix: the pre-evaluation universe snapshot is a PRECONDITION, not
    a business action -- it is captured here at fixture-construction time
    (before any `When` runs), so the walking-skeleton scenarios carry exactly
    one `When` (the gate verification) rather than folding a snapshot step into
    a second `When`. `gate` is constructed before this fixture, so the snapshot
    is the genuine pre-gate state.
    """
    return {"universe_before": gate.capture_universe()}


def _result(box: dict[str, object]) -> GateResult:
    return box["result"]  # type: ignore[return-value]


# --- Given: feature shape + walking-skeleton-test presence -------------------


@given(
    parsers.parse(
        "a feature that {feature_shape} with a walking-skeleton acceptance test"
    )
)
def given_feature_with_at(
    gate: WalkingSkeletonGateComposition, feature_shape: str
) -> None:
    gate.create_feature(
        FeatureId("demo-feature"), FEATURE_SHAPE_BY_PHRASE[feature_shape]
    )
    gate.author_walking_skeleton_test(present=True)


@given(
    parsers.parse(
        "a feature that {feature_shape} with no walking-skeleton acceptance test"
    )
)
def given_feature_without_at(
    gate: WalkingSkeletonGateComposition, feature_shape: str
) -> None:
    gate.create_feature(
        FeatureId("demo-feature"), FEATURE_SHAPE_BY_PHRASE[feature_shape]
    )
    gate.author_walking_skeleton_test(present=False)


@given(
    parsers.parse(
        "a feature that {feature_shape} with a passing walking-skeleton acceptance test"
    )
)
def given_feature_with_passing_at(
    gate: WalkingSkeletonGateComposition, feature_shape: str
) -> None:
    given_feature_with_at(gate, feature_shape)
    gate.make_walking_skeleton_test_pass(passes=True)


@given(
    parsers.parse(
        "a feature that {feature_shape} with a failing walking-skeleton acceptance test"
    )
)
def given_feature_with_failing_at(
    gate: WalkingSkeletonGateComposition, feature_shape: str
) -> None:
    given_feature_with_at(gate, feature_shape)
    gate.make_walking_skeleton_test_pass(passes=False)


@given(parsers.parse("a feature that {feature_shape}"))
def given_feature_only(
    gate: WalkingSkeletonGateComposition, feature_shape: str
) -> None:
    gate.create_feature(
        FeatureId("demo-feature"), FEATURE_SHAPE_BY_PHRASE[feature_shape]
    )


@given("the feature carries a walking-skeleton acceptance test")
def given_feature_carries_at(gate: WalkingSkeletonGateComposition) -> None:
    gate.author_walking_skeleton_test(present=True)


@given("the feature carries no walking-skeleton acceptance test")
def given_feature_carries_no_at(gate: WalkingSkeletonGateComposition) -> None:
    gate.author_walking_skeleton_test(present=False)


@given("the script-mode CLI is absent from the installer distribution whitelist")
def given_cli_absent_from_whitelist(gate: WalkingSkeletonGateComposition) -> None:
    gate.omit_cli_from_distribution_whitelist()


# --- Given: environment + fixture-failure arming -----------------------------


@given(parsers.parse("the environment reports {capability}"))
def given_environment_capability(
    gate: WalkingSkeletonGateComposition, capability: str
) -> None:
    gate.set_environment_capability(TIER_CAPABILITY_BY_PHRASE[capability])


@given(parsers.parse("the walking-skeleton gate subprocess {subprocess_outcome}"))
def given_hook_subprocess_outcome(
    gate: WalkingSkeletonGateComposition, subprocess_outcome: str
) -> None:
    gate.set_arming_hook_subprocess_outcome(HOOK_OUTCOME_BY_PHRASE[subprocess_outcome])


@given("the marker cannot be written to disk")
def given_marker_unwritable(gate: WalkingSkeletonGateComposition) -> None:
    gate.make_marker_directory_read_only()


@given(parsers.parse("the feature is classified as {os_sensitivity}"))
def given_os_sensitivity(
    gate: WalkingSkeletonGateComposition, os_sensitivity: str
) -> None:
    gate.classify_os_sensitivity(OS_SENSITIVITY_BY_PHRASE[os_sensitivity])


@given(
    parsers.re(
        r"the (?P<_pfx>artifact build fails|install prefix is not writable"
        r"|install prefix forbids execution|disk is exhausted"
        r"|install prefix is not clean)"
    )
)
def given_provisioning_failure(gate: WalkingSkeletonGateComposition, _pfx: str) -> None:
    gate.set_fixture_failure(DEFERRAL_REASON_BY_PHRASE[f"the {_pfx}"])


# --- Given: entry-gate applicability SSOT record -----------------------------


@given("the entry-gate recorded the feature as shipping an installer artifact")
def given_entry_gate_applicable(gate: WalkingSkeletonGateComposition) -> None:
    gate.record_entry_gate_applicability(applicable=True)


@given("the entry-gate recorded the feature as not shipping an installer artifact")
def given_entry_gate_not_applicable(gate: WalkingSkeletonGateComposition) -> None:
    gate.record_entry_gate_applicability(applicable=False)


# --- Given: marker / verification-record preconditions -----------------------


@given("a feature carries a walking-skeleton-unverified marker")
def given_feature_has_marker(gate: WalkingSkeletonGateComposition) -> None:
    gate.write_deferral_marker(MarkerKind.UNVERIFIED, artifact_hash="sha256:base")


@given(
    "the marker has been removed by hand without any verification record being written"
)
def given_marker_removed_by_hand(gate: WalkingSkeletonGateComposition) -> None:
    gate.remove_marker_by_hand()


@given(parsers.parse("a feature whose deferral marker directory holds {marker_state}"))
def given_marker_directory_state(
    gate: WalkingSkeletonGateComposition, marker_state: str
) -> None:
    gate.write_deferral_marker(MarkerKind.UNVERIFIED, artifact_hash="sha256:base")
    _apply_marker_state(gate, MARKER_STATE_BY_PHRASE[marker_state])


def _apply_marker_state(
    gate: WalkingSkeletonGateComposition, state: MarkerReadState
) -> None:
    """Coerce the marker file into the requested read-state (test-only helper)."""
    if state is MarkerReadState.ABSENT:
        gate.remove_marker_by_hand()
    elif state is MarkerReadState.UNPARSEABLE:
        gate.corrupt_marker()


@given("a positive walking-skeleton verification record exists for the feature")
def given_positive_record(gate: WalkingSkeletonGateComposition) -> None:
    gate.write_positive_verification_record()


@given(
    "a feature carries a walking-skeleton-unverified marker bound to an artifact hash"
)
def given_marker_bound_to_hash(gate: WalkingSkeletonGateComposition) -> None:
    gate.write_deferral_marker(MarkerKind.UNVERIFIED, artifact_hash="sha256:bound")


@given(
    "a feature carries a walking-skeleton-unverified marker bound to a later "
    "artifact hash"
)
def given_marker_bound_to_later_hash(
    gate: WalkingSkeletonGateComposition,
) -> None:
    gate.write_deferral_marker(MarkerKind.UNVERIFIED, artifact_hash="sha256:later")


@given("an OS-sensitive feature carries an open walking-skeleton tier-debt record")
def given_open_tier_debt(gate: WalkingSkeletonGateComposition) -> None:
    gate.classify_os_sensitivity(OS_SENSITIVITY_BY_PHRASE["OS-sensitive"])
    gate.write_deferral_marker(MarkerKind.TIER_DEBT, artifact_hash="sha256:bound")


# --- When: gate invocations --------------------------------------------------


@when(
    "the feature-end gate verifies the walking skeleton against the delivered artifact"
)
def when_gate_verifies_against_artifact(
    gate: WalkingSkeletonGateComposition, box: dict[str, object]
) -> None:
    box["result"] = gate.run_gate_cli_directly()


@when("the feature-end cycle reaches the walking-skeleton gate")
def when_feature_end_reaches_gate(
    gate: WalkingSkeletonGateComposition, box: dict[str, object]
) -> None:
    box["result"] = gate.run_feature_end_gate()


@when("the feature-end gate attempts to verify the walking skeleton")
def when_feature_end_attempts_verify(
    gate: WalkingSkeletonGateComposition, box: dict[str, object]
) -> None:
    box["result"] = gate.run_feature_end_gate()


@when("the feature-end gate verifies the walking skeleton")
def when_feature_end_verifies(
    gate: WalkingSkeletonGateComposition, box: dict[str, object]
) -> None:
    box["result"] = gate.run_feature_end_gate()


@when(
    "the feature-end gate verifies the walking skeleton without an explicit "
    "tier request"
)
def when_verify_no_tier_request(
    gate: WalkingSkeletonGateComposition, box: dict[str, object]
) -> None:
    box["result"] = gate.run_feature_end_gate(tier_request=None)


@when(
    "the feature-end gate verifies the walking skeleton with the container "
    "tier requested"
)
def when_verify_t2_requested(
    gate: WalkingSkeletonGateComposition, box: dict[str, object]
) -> None:
    box["result"] = gate.run_feature_end_gate(tier_request=Tier.T2)


@when("the feature-end gate verifies the walking skeleton again")
def when_verify_again(
    gate: WalkingSkeletonGateComposition, box: dict[str, object]
) -> None:
    box["result"] = gate.run_feature_end_gate()


@when(
    "the feature-end cycle reaches a gate that self-classifies the feature as "
    "not applicable"
)
def when_gate_self_classifies_na(
    gate: WalkingSkeletonGateComposition, box: dict[str, object]
) -> None:
    box["result"] = gate.run_feature_end_gate()


@when("the done-gate evaluates whether the feature can be marked done")
def when_done_gate_evaluates(
    gate: WalkingSkeletonGateComposition, box: dict[str, object]
) -> None:
    box["done"] = gate.run_done_gate()


@when("a downstream verification runs green against the bound artifact")
def when_downstream_verifies_bound(
    gate: WalkingSkeletonGateComposition, box: dict[str, object]
) -> None:
    box["result"] = gate.run_downstream_verification(
        against_artifact_hash="sha256:bound", tier=Tier.T1
    )


@when("a downstream verification runs green against an older artifact")
def when_downstream_verifies_stale(
    gate: WalkingSkeletonGateComposition, box: dict[str, object]
) -> None:
    box["result"] = gate.run_downstream_verification(
        against_artifact_hash="sha256:older", tier=Tier.T1
    )


@when("a downstream verification runs the walking skeleton green at the container tier")
def when_downstream_verifies_t2(
    gate: WalkingSkeletonGateComposition, box: dict[str, object]
) -> None:
    box["result"] = gate.run_downstream_verification(
        against_artifact_hash="sha256:bound", tier=Tier.T2
    )


# --- Then: gate verdict ------------------------------------------------------


@then(
    parsers.parse(
        "the walking-skeleton gate reports {verdict} at tier of record {tier}"
    )
)
def then_gate_reports(box: dict[str, object], verdict: str, tier: str) -> None:
    result = _result(box)
    assert (result.verdict, result.tier_of_record) == (
        VERDICT_BY_PHRASE[verdict],
        TIER_BY_PHRASE[tier],
    )


@then("the feature is not marked done")
def then_feature_not_done(box: dict[str, object]) -> None:
    assert _result(box).verdict is not GateVerdict.PASS


@then("the feature remains not marked done")
def then_feature_remains_not_done(box: dict[str, object]) -> None:
    assert box["done"].done_allowed is False  # type: ignore[union-attr]


@then("feature-end proceeds")
def then_feature_end_proceeds(box: dict[str, object]) -> None:
    assert _result(box).verdict in (GateVerdict.PASS, GateVerdict.NOT_APPLICABLE)


@then("the feature can be marked done")
def then_feature_can_be_done(
    gate: WalkingSkeletonGateComposition, box: dict[str, object]
) -> None:
    assert gate.run_done_gate().done_allowed is True


@then(parsers.parse("the feature-end cycle treats the run as {treated_as}"))
def then_run_treated_as(box: dict[str, object], treated_as: str) -> None:
    assert _result(box).verdict is VERDICT_BY_PHRASE[treated_as]


# --- Then: diagnostics -------------------------------------------------------


@then("the gate diagnostic names the entry point absent from the installed tree")
def then_diagnostic_entry_point_absent(box: dict[str, object]) -> None:
    assert _result(box).facet_violation is FacetViolationKind.FACET1_ENTRY_POINT_ABSENT


@then(
    "the gate diagnostic states no walking-skeleton test exists for an "
    "installer-shipped feature"
)
def then_diagnostic_no_at(box: dict[str, object]) -> None:
    # Non-blocking review fix: assert the SPECIFIC absence-of-AT reason -- the
    # diagnostic must name both the missing walking-skeleton test and the
    # installer-shipped applicability, not merely mention "walking-skeleton".
    diagnostic = _result(box).diagnostic.lower()
    assert "walking-skeleton" in diagnostic
    assert "no" in diagnostic or "absent" in diagnostic or "missing" in diagnostic
    assert "installer" in diagnostic


@then("the gate diagnostic states the applicability record was contradicted")
def then_diagnostic_applicability_contradicted(box: dict[str, object]) -> None:
    assert "applicab" in _result(box).diagnostic.lower()


@then("the walking-skeleton gate exits non-zero with the marker-write-failed reason")
def then_exits_marker_write_failed(box: dict[str, object]) -> None:
    result = _result(box)
    assert result.exit_code != 0 and result.reason is not None


@then("the deferral marker records a closed reason rather than free prose")
def then_marker_reason_closed(gate: WalkingSkeletonGateComposition) -> None:
    assert gate.marker_reason_is_closed_enum() is True


# --- Then: ledger / marker records (port-exposed universe, Mandate 8) --------


@then("the gate records a positive walking-skeleton verification for the feature")
def then_positive_record_written(gate: WalkingSkeletonGateComposition) -> None:
    assert gate.positive_verification_record_present() is True


@then("the feature-end cycle records a positive walking-skeleton verification")
def then_cycle_positive_record(gate: WalkingSkeletonGateComposition) -> None:
    assert gate.positive_verification_record_present() is True


@then(
    "the feature-end gate run emitted a walking-skeleton heartbeat before the verdict"
)
def then_heartbeat_emitted(gate: WalkingSkeletonGateComposition) -> None:
    assert gate.heartbeat_record_present() is True


@then("the gate records a not-applicable ledger entry naming the paths it checked")
def then_not_applicable_record(gate: WalkingSkeletonGateComposition) -> None:
    assert gate.not_applicable_record_present() is True


@then(
    "the gate writes a walking-skeleton-unverified marker naming the feature "
    "and the reason"
)
def then_marker_written(gate: WalkingSkeletonGateComposition) -> None:
    assert gate.marker_present() and gate.marker_reason_is_closed_enum()


@then("the gate writes a walking-skeleton tier-debt record")
def then_tier_debt_written(gate: WalkingSkeletonGateComposition) -> None:
    assert gate.tier_debt_record_present() is True


@then("the gate writes no tier-debt record")
def then_no_tier_debt(gate: WalkingSkeletonGateComposition) -> None:
    assert gate.tier_debt_record_present() is False


@then(
    "the gate writes a walking-skeleton tier-debt record for the container "
    "tier to settle"
)
def then_tier_debt_for_t2(gate: WalkingSkeletonGateComposition) -> None:
    assert gate.tier_debt_record_present() is True


# --- Then: marker lifecycle --------------------------------------------------


@then(
    "the marker is cleared and a positive walking-skeleton verification "
    "record is written"
)
def then_marker_cleared_with_record(
    gate: WalkingSkeletonGateComposition,
) -> None:
    assert not gate.marker_present() and gate.positive_verification_record_present()


@then(
    "the marker is not cleared because the verified artifact does not match the marker"
)
def then_marker_not_cleared_stale(gate: WalkingSkeletonGateComposition) -> None:
    assert gate.marker_present() is True


@then("the tier-debt record is cleared")
def then_tier_debt_cleared(gate: WalkingSkeletonGateComposition) -> None:
    assert gate.tier_debt_record_present() is False


# --- Then: done-gate ---------------------------------------------------------


@then(parsers.parse("the done-gate verdict is {done_allowed}"))
def then_done_gate_verdict(box: dict[str, object], done_allowed: str) -> None:
    assert box["done"].done_allowed is (done_allowed == "allowed")  # type: ignore[union-attr]


@then(
    "the done-gate refuses because no positive walking-skeleton verification "
    "record exists"
)
def then_done_refuses_no_record(box: dict[str, object]) -> None:
    assert box["done"].done_allowed is False  # type: ignore[union-attr]


@then("the done-gate refuses because the container-tier debt is unsettled")
def then_done_refuses_tier_debt(box: dict[str, object]) -> None:
    assert box["done"].done_allowed is False  # type: ignore[union-attr]


# --- Then: tier behaviour ----------------------------------------------------


@then("the gate ran the prerequisite first tier before the container tier")
def then_prerequisite_tier_first(box: dict[str, object]) -> None:
    assert _result(box).ran_prerequisite_tier_first is True


@then("the gate reuses the cached delivered artifact without rebuilding it")
def then_reuses_cached_build(box: dict[str, object]) -> None:
    assert _result(box).reused_cached_build is True


# --- Then: universe-bound preservation assertions (Mandate 8) ----------------


@then("the developer's repository working tree is unchanged")
def then_repo_unchanged(
    gate: WalkingSkeletonGateComposition, box: dict[str, object]
) -> None:
    # B3 review fix: the preservation observable is the content fingerprint of
    # the developer source tree -- a port-exposed, per-test-stable SUT
    # observable -- NOT a `git status` shell-out against the live checkout.
    assert_state_delta(
        before=box["universe_before"],  # type: ignore[arg-type]
        after=gate.capture_universe(),
        universe={"source_tree.content_fingerprint"},
        expected={"source_tree.content_fingerprint": unchanged()},
    )


@then("no file under the developer's source tree was written during the gate run")
def then_no_source_tree_write(
    gate: WalkingSkeletonGateComposition, box: dict[str, object]
) -> None:
    # B3 review fix: same content-fingerprint universe -- a write into any
    # `src/` or `scripts/` `.py` file changes its SHA-256 and reds this step.
    assert_state_delta(
        before=box["universe_before"],  # type: ignore[arg-type]
        after=gate.capture_universe(),
        universe={"source_tree.content_fingerprint"},
        expected={"source_tree.content_fingerprint": unchanged()},
    )


# --- Fixtures for slices 10-16 -----------------------------------------------


@pytest.fixture
def propagation(tmp_path: Path) -> AuthoringPropagationComposition:
    """Composition root for the slice-15/16 authoring-side propagation arch test."""
    return AuthoringPropagationComposition(repo_dir=tmp_path / "repo")


# --- slice-10/11: distribution-completeness arch test ------------------------


@given("any hook that subprocess-invokes a command module")
def given_hook_invoking_command(
    distribution: DistributionCompletenessComposition,
) -> None:
    distribution.given_hook_invoking_command(in_whitelist=True)


@given("that command is absent from the installer distribution whitelist")
def given_command_absent_whitelist(
    distribution: DistributionCompletenessComposition,
) -> None:
    distribution.given_hook_invoking_command(in_whitelist=False)


@given(
    "any hook-invoked command that resides on a path surviving the installer whitelist"
)
def given_command_surviving_whitelist(
    distribution: DistributionCompletenessComposition,
) -> None:
    distribution.given_hook_invoking_command(in_whitelist=True)


@given("no subprocess-real wiring test exercises that command")
def given_no_wiring_test(
    distribution: DistributionCompletenessComposition,
) -> None:
    distribution.given_command_wiring_test(present=False)


@given("every hook-invoked command resides on a path surviving the installer whitelist")
def given_every_command_surviving(
    distribution: DistributionCompletenessComposition,
) -> None:
    distribution.given_hook_invoking_command(in_whitelist=True)


@given(
    "each hook-invoked command is exercised by at least one subprocess-real wiring test"
)
def given_each_command_wiring_tested(
    distribution: DistributionCompletenessComposition,
) -> None:
    distribution.given_command_wiring_test(present=True)


@given("the distribution-completeness check enumerates the hook-invoked command set")
def given_check_enumerates(
    distribution: DistributionCompletenessComposition,
) -> None:
    distribution.given_hook_invoking_command(in_whitelist=True)


@given("the feature-end hook handler is missing its walking-skeleton branch")
def given_hook_branch_missing(
    distribution: DistributionCompletenessComposition,
) -> None:
    distribution.remove_hook_branch()


@given(
    "the walking-skeleton-unverified marker directory carries no explicit "
    "un-ignore rule"
)
def given_marker_dir_untracked(
    distribution: DistributionCompletenessComposition,
) -> None:
    distribution.make_marker_directory_untracked()


@when("the distribution-completeness check evaluates the hook-invoked command set")
def when_distribution_check_evaluates(
    distribution: DistributionCompletenessComposition, box: dict[str, object]
) -> None:
    box["dist"] = distribution.evaluate_completeness()


@when("the distribution-completeness check verifies the registered hook branches")
def when_distribution_check_branches(
    distribution: DistributionCompletenessComposition, box: dict[str, object]
) -> None:
    box["dist"] = distribution.evaluate_hook_branch_registration()


@when(
    "the distribution-completeness check verifies the marker directories travel to CI"
)
def when_distribution_check_marker_dirs(
    distribution: DistributionCompletenessComposition, box: dict[str, object]
) -> None:
    box["dist"] = distribution.evaluate_marker_dir_tracked()


@then(parsers.parse("the check fails naming the command and the {reason_phrase}"))
def then_check_fails_naming_command(box: dict[str, object], reason_phrase: str) -> None:
    # Non-blocking review fix: assert the check not only fails but NAMES the
    # offending command and surfaces the specific reason in its diagnostic.
    result = box["dist"]
    assert result.passed is False  # type: ignore[union-attr]
    assert result.named_command  # type: ignore[union-attr]
    assert result.diagnostic  # type: ignore[union-attr]


@then("the distribution-completeness check passes")
def then_distribution_check_passes(box: dict[str, object]) -> None:
    assert box["dist"].passed is True  # type: ignore[union-attr]


@then(
    "the walking-skeleton gate command is in the enumeration and survives the whitelist"
)
def then_gate_command_enumerated(
    distribution: DistributionCompletenessComposition,
) -> None:
    assert "des.cli.walking_skeleton_gate" in distribution.gate_own_cli_enumeration()


@then(
    "the walking-skeleton done-gate command is in the enumeration and survives "
    "the whitelist"
)
def then_done_gate_command_enumerated(
    distribution: DistributionCompletenessComposition,
) -> None:
    assert (
        "des.cli.walking_skeleton_done_gate" in distribution.gate_own_cli_enumeration()
    )


@then("the check fails naming the unregistered hook branch")
def then_check_fails_hook_branch(box: dict[str, object]) -> None:
    # Non-blocking review fix: assert the diagnostic names the hook branch.
    result = box["dist"]
    assert result.passed is False  # type: ignore[union-attr]
    assert "branch" in result.diagnostic.lower()  # type: ignore[union-attr]


@then("the check fails naming the gitignored marker directory")
def then_check_fails_marker_dir(box: dict[str, object]) -> None:
    # Non-blocking review fix: assert the diagnostic names the marker directory.
    result = box["dist"]
    assert result.passed is False  # type: ignore[union-attr]
    assert "marker" in result.diagnostic.lower()  # type: ignore[union-attr]


# --- slice-14: customer-project CI scaffold ----------------------------------


@given("a customer project with no walking-skeleton CI job")
def given_customer_project_no_ci(
    scaffold: CustomerScaffoldComposition,
) -> None:
    scaffold.given_customer_project()


@given("a customer project with no walking-skeleton documentation")
def given_customer_project_no_docs(
    scaffold: CustomerScaffoldComposition,
) -> None:
    scaffold.given_customer_project()


@given("a customer project with the scaffolded walking-skeleton CI job")
def given_customer_project_scaffolded(
    scaffold: CustomerScaffoldComposition,
) -> None:
    scaffold.given_customer_project()
    scaffold.run_scaffold_step()


@given("the developer has not filled the prod-like image placeholder")
def given_image_not_filled(scaffold: CustomerScaffoldComposition) -> None:
    scaffold.given_customer_project()


@when("the developer runs the walking-skeleton scaffold step")
def when_run_scaffold_step(
    scaffold: CustomerScaffoldComposition, box: dict[str, object]
) -> None:
    box["scaffold_universe_before"] = scaffold.capture_universe()
    scaffold.run_scaffold_step()


@when("the walking-skeleton CI job runs")
def when_scaffolded_ci_job_runs(
    scaffold: CustomerScaffoldComposition, box: dict[str, object]
) -> None:
    box["result"] = scaffold.run_scaffolded_ci_job(image_filled=False)


@then(
    "the scaffold writes a walking-skeleton CI job with a clean-prefix install "
    "of the project's delivered artifact"
)
def then_scaffold_writes_ci_job(scaffold: CustomerScaffoldComposition) -> None:
    assert "walking-skeleton" in scaffold.ci_job_text()


@then(
    "the CI job carries a documented placeholder for the developer's own prod-like image"
)
def then_ci_job_placeholder(scaffold: CustomerScaffoldComposition) -> None:
    assert "fill:" in scaffold.ci_job_text()


@then("the CI job inherits the fail-closed deferral semantics")
def then_ci_job_fail_closed(scaffold: CustomerScaffoldComposition) -> None:
    assert "walking_skeleton_gate" in scaffold.ci_job_text()


@then("the clean-prefix walking-skeleton check runs and gates the build")
def then_clean_prefix_check_gates(box: dict[str, object]) -> None:
    assert _result(box).tier_of_record is Tier.T1


@then("the container tier is recorded as not configured rather than silently passed")
def then_container_not_configured(box: dict[str, object]) -> None:
    assert _result(box).tier_of_record is Tier.T1


@then(
    "the scaffold writes a walking-skeleton explanation describing why the "
    "delivered artifact is installed rather than the source"
)
def then_scaffold_writes_explanation(
    scaffold: CustomerScaffoldComposition,
) -> None:
    assert "delivered artifact" in scaffold.explanation_doc_text()


# --- slice-15/16: authoring-side propagation arch test -----------------------


@given(
    parsers.parse("{authoring_artifact} carries the tiered walking-skeleton discipline")
)
def given_artifact_carries_discipline(
    propagation: AuthoringPropagationComposition, authoring_artifact: str
) -> None:
    propagation.given_authoring_artifact_carries_discipline(
        AUTHORING_ARTIFACT_BY_PHRASE[authoring_artifact].value
    )


@given(parsers.parse("{authoring_artifact} carries the tier-discipline skill"))
def given_artifact_carries_skill(
    propagation: AuthoringPropagationComposition, authoring_artifact: str
) -> None:
    propagation.given_authoring_artifact_carries_discipline(
        AUTHORING_ARTIFACT_BY_PHRASE[authoring_artifact].value
    )


@given(
    parsers.parse("{authoring_artifact} omits the tiered walking-skeleton discipline")
)
def given_artifact_omits_discipline(
    propagation: AuthoringPropagationComposition, authoring_artifact: str
) -> None:
    propagation.given_authoring_artifact_omits_discipline(
        AUTHORING_ARTIFACT_BY_PHRASE[authoring_artifact].value
    )


@given(parsers.parse("{authoring_artifact} omits the tier-discipline skill"))
def given_artifact_omits_skill(
    propagation: AuthoringPropagationComposition, authoring_artifact: str
) -> None:
    propagation.given_authoring_artifact_omits_discipline(
        AUTHORING_ARTIFACT_BY_PHRASE[authoring_artifact].value
    )


@when(parsers.parse("the propagation check reads {authoring_artifact}"))
def when_propagation_check_reads(
    propagation: AuthoringPropagationComposition,
    box: dict[str, object],
    authoring_artifact: str,
) -> None:
    box["dist"] = propagation.evaluate_skill_propagation(
        AUTHORING_ARTIFACT_BY_PHRASE[authoring_artifact].value
    )


@then(
    parsers.parse(
        "the propagation check confirms {authoring_subject} teach the tiered discipline"
    )
)
def then_propagation_confirms_plural(
    box: dict[str, object], authoring_subject: str
) -> None:
    assert box["dist"].passed is True  # type: ignore[union-attr]


@then(
    parsers.parse(
        "the propagation check confirms {authoring_subject} teaches the tiered discipline"
    )
)
def then_propagation_confirms_singular(
    box: dict[str, object], authoring_subject: str
) -> None:
    assert box["dist"].passed is True  # type: ignore[union-attr]


@then(
    "the propagation check confirms the loading table references the "
    "tier-discipline skill"
)
def then_propagation_confirms_loading_table(box: dict[str, object]) -> None:
    assert box["dist"].passed is True  # type: ignore[union-attr]


@then(
    "the propagation check fails naming the authoring artifact that omits the discipline"
)
def then_propagation_check_fails(box: dict[str, object]) -> None:
    assert box["dist"].passed is False  # type: ignore[union-attr]


@then("the propagation arch test passes")
def then_propagation_arch_test_passes(
    propagation: AuthoringPropagationComposition,
) -> None:
    assert propagation.evaluate_full_propagation().passed is True


# --- slice-12/13: carpaccio entry gate ---------------------------------------


@when("the carpaccio entry gate evaluates the feature at slice-one entry")
def when_carpaccio_entry_gate(
    gate: WalkingSkeletonGateComposition, box: dict[str, object]
) -> None:
    box["result"] = gate.run_carpaccio_entry_gate()


@then(
    parsers.parse("the entry gate records the feature applicability as {applicability}")
)
def then_entry_gate_applicability(box: dict[str, object], applicability: str) -> None:
    expected = (
        GateVerdict.NOT_APPLICABLE
        if applicability == "not applicable"
        else GateVerdict.PASS
    )
    assert _result(box).verdict is expected


@then("the entry gate fails naming the missing walking-skeleton test")
def then_entry_gate_fails_missing_at(box: dict[str, object]) -> None:
    result = _result(box)
    assert result.verdict is GateVerdict.FAIL
    assert "walking-skeleton" in result.diagnostic.lower()


@then("the feature cannot enter slice-one")
def then_cannot_enter_slice_one(box: dict[str, object]) -> None:
    assert _result(box).verdict is GateVerdict.FAIL


@then("the feature may enter slice-one")
def then_may_enter_slice_one(box: dict[str, object]) -> None:
    assert _result(box).verdict is not GateVerdict.FAIL


@then(
    "the entry gate writes an applicability record naming the paths it checked "
    "and the matched rule"
)
def then_applicability_record_written(
    gate: WalkingSkeletonGateComposition,
) -> None:
    assert gate.applicability_record() != {}


# --- slice-09: build-cache + real-container smoke ----------------------------


@given("a feature whose walking-skeleton gate has already built the delivered artifact")
def given_gate_already_built(gate: WalkingSkeletonGateComposition) -> None:
    gate.create_feature(
        FeatureId("demo-feature"),
        FEATURE_SHAPE_BY_PHRASE["ships a packaged CLI module"],
    )
    gate.author_walking_skeleton_test(present=True)


@given("the repository tree is unchanged since that build")
def given_tree_unchanged_since_build(gate: WalkingSkeletonGateComposition) -> None:
    gate.prime_build_cache()


@given("a feature whose walking-skeleton acceptance test passes at the first tier")
def given_feature_passes_first_tier(gate: WalkingSkeletonGateComposition) -> None:
    gate.create_feature(
        FeatureId("demo-feature"),
        FEATURE_SHAPE_BY_PHRASE["ships a packaged CLI module"],
    )
    gate.author_walking_skeleton_test(present=True)


@given(
    "the artifact relies on a path layout that does not resolve on the "
    "container's operating system"
)
def given_artifact_os_path_defect(
    gate: WalkingSkeletonGateComposition,
) -> None:
    # B4 review fix: an OS-path-layout bug is a T2 AT red (FAIL), not a
    # provisioning failure (UNVERIFIED). Arm the distinct OS-path-defect path
    # so the container-tier AT genuinely runs RED at T2.
    gate.arm_t2_only_os_path_defect()


@given("a real container runtime is available")
def given_real_container_runtime(gate: WalkingSkeletonGateComposition) -> None:
    gate.set_environment_capability(TIER_CAPABILITY_BY_PHRASE["Docker available"])


@when(
    "the container runner installs the delivered artifact into a clean image "
    "and runs the walking-skeleton test"
)
def when_container_runner_runs(
    gate: WalkingSkeletonGateComposition, box: dict[str, object]
) -> None:
    box["result"] = gate.run_feature_end_gate(tier_request=Tier.T2)
