"""Step definitions for fix-atdd-pure-spine-dogfood-defects acceptance tests.

Three slices, three `.feature` files, one shared step vocabulary (Mandate-12).
Step bodies delegate to `SpineDogfoodComposition` -- no inline business logic
(Mandate-12 criterion 3). Domain nouns are typed via `domain_types` (criterion
1); the composition service signatures consume those typed parameters
(criterion 2).

slice-01 + slice-02 scenarios are RED scaffolds -- the production fixes do not
exist yet. Each scaffold step that asserts an unimplemented contract raises
`AssertionError` (MISSING_FUNCTIONALITY) so the Red Gate classifies RED, not
BROKEN. They are collected `xfail(strict=False)` via the marker below so the
suite stays GREEN until DELIVER's A_GREEN_ATS turns them green.

slice-00's AT(3) is a RED probe authored to be run + observed by DELIVER.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition import SpineDogfoodComposition
from .domain_types import (
    EMPTY_DIGEST,
    CollectScope,
    CollectVerdict,
    DispatchPhase,
    DispatchRecognition,
    DispatchScope,
    GuardOutcome,
)


# Bind all three slice feature files.
scenarios(
    "../slice-00-contract-suite-collects-clean.feature",
    "../slice-01-e2-gate-verifies-real-scope.feature",
    "../slice-02-feature-end-cycle-dispatchable.feature",
)

# slice-01 + slice-02 scenarios are marked xfail (RED scaffold) by the
# `pytest_collection_modifyitems` hook in conftest.py -- the fixes do not exist
# yet. DELIVER removes a slice's mark as it turns that slice green.


@pytest.fixture
def composition() -> SpineDogfoodComposition:
    """The production composition root for the three defect fixes."""
    return SpineDogfoodComposition()


# ===========================================================================
# slice-00 -- the contract suite collects clean
# ===========================================================================


@given(
    "a contract test tree with all path and packaging drift repaired",
    target_fixture="probe_root",
)
def _given_repaired_tree(composition: SpineDogfoodComposition):
    """Precondition: the real repo tree (post-slice-00) collects clean.

    AT(1)/AT(2) probe the real repo -- the production fix
    (`consider_namespace_packages = true`) is in the working tree, so the
    contract suite collects clean. Returning the repo path makes the shared
    `When` step probe THIS scope.
    """
    return composition.repo


@given(
    "a contract test module with a deliberately broken import",
    target_fixture="probe_root",
)
def _given_broken_import_module(composition: SpineDogfoodComposition, tmp_path):
    """Precondition: a real on-disk tree carrying a deliberately broken import.

    AT(3) genuinely materialises the broken-import condition -- it does NOT
    probe the clean repo. The composition writes a synthetic contract tree
    whose one module `import`s a non-existent module; `make_test_tree` anchors
    it MECHANICALLY to pytest collection-error exit 2 before the probe runs.
    Returning the broken tree path makes the shared `When` step probe IT.
    """
    return composition.make_test_tree(tmp_path, CollectScope.COLLECTION_ERROR)


@when("the operator collects the whole contract suite", target_fixture="collect")
def _when_collect_contract_suite(composition: SpineDogfoodComposition, probe_root):
    """Drive the real `pytest --collect-only` contract probe over `probe_root`.

    `probe_root` is whatever scope the scenario's `Given` established -- the
    real repo for AT(1)/AT(2), the broken-import tree for AT(3). The probe
    therefore genuinely exercises the condition the scenario set up.
    """
    return composition.probe_contract_collection(probe_root)


@then("the collection reports zero collection errors")
def _then_zero_collection_errors(collect) -> None:
    assert collect.verdict is CollectVerdict.CLEAN, (
        f"contract tree still has {collect.error_count} collection error(s) "
        "-- slice-00 not yet delivered"
    )


@then("the collection covers a non-empty set of contract tests")
def _then_non_empty_collection(collect) -> None:
    assert collect.node_id_count > 0, "contract collection covered zero tests"


@then("every contract test module imports and contributes its tests")
def _then_every_module_collects(collect) -> None:
    assert collect.verdict is CollectVerdict.CLEAN, (
        "at least one contract module still fails to import -- slice-00 "
        "not yet delivered"
    )


@then("no module is silently dropped from the contract scope")
def _then_no_module_dropped(collect) -> None:
    # Primary, design-mandated signal: the exit code (residuality S-8, DoD-2).
    # `exit_code != 2` == nothing errored out of the contract scope.
    assert collect.verdict is CollectVerdict.CLEAN, (
        f"contract collection exited {collect.exit_code} -- a module was "
        "dropped from the contract scope (slice-00 not yet delivered)"
    )
    # Defence-in-depth corroboration only -- never the sole assertion (HIGH 4).
    assert collect.error_count == 0, (
        f"exit code clean but {collect.error_count} collection-error line(s) "
        "parsed -- exit-code / summary-line disagreement, investigate"
    )


@then("the collection reports a non-zero collection-error count")
def _then_collection_error_count_nonzero(collect) -> None:
    # Primary, design-mandated signal: the exit code (residuality S-8, DoD-2).
    # A genuine collection error is exit 2 -- exit-code-exact, never a parse.
    assert collect.verdict is CollectVerdict.HAS_ERRORS, (
        f"a deliberately broken import yielded exit {collect.exit_code}, not "
        "the collection-error exit 2 -- it was NOT reported as a collection error"
    )
    # Defence-in-depth corroboration only -- never the sole assertion (HIGH 4).
    assert collect.error_count > 0, (
        "exit code signalled a collection error but the summary line reported "
        "zero -- exit-code / summary-line disagreement, investigate"
    )


@then("the collection signals failure through a collection-error exit code")
def _then_collection_error_exit_code(collect) -> None:
    assert collect.exit_code == 2, (
        f"expected pytest collection-error exit 2, got {collect.exit_code}"
    )


# ===========================================================================
# slice-01 -- the E2 contract gate verifies a real, non-empty scope
# ===========================================================================


@given("a contract test tree that collects clean", target_fixture="gate_repo")
def _given_clean_tree_for_gate(composition: SpineDogfoodComposition):
    """Precondition: the repo (post-slice-00) collects clean."""
    return composition.repo


_UNTRUSTWORTHY_SCOPE = {
    "broken by a collection error": CollectScope.COLLECTION_ERROR,
    "empty while reporting a populated suite": CollectScope.ZERO_NODES_EXIT_ZERO,
}


@given(
    parsers.parse("a contract test tree whose collection is {collection_condition}"),
    target_fixture="gate_repo",
)
def _given_untrustworthy_collection(
    composition: SpineDogfoodComposition, collection_condition: str, tmp_path
):
    """Precondition: a tree in an untrustworthy collection scope.

    COLLECTION_ERROR -> a synthetic tree with a deliberately broken import.
    ZERO_NODES_EXIT_ZERO -> a synthetic tree that reports a populated suite
    while zero `::` node-ids parse (a tree-local conftest empties
    `session.items` after the count is fixed) -- the exact populated-but-
    zero-node-ids state the guard fails closed on. It is NOT the real repo:
    once slice-01's `_collect_node_ids` fix lands the real repo collects
    cleanly and emits node-ids, so it can no longer reproduce this state.
    The synthetic tree reproduces it independently of the fix under test.
    """
    return composition.test_tree_for_scope(
        tmp_path, _UNTRUSTWORTHY_SCOPE[collection_condition]
    )


@given(
    "a contract test tree with no contract-marked tests at all",
    target_fixture="gate_repo",
)
def _given_genuinely_empty_tree(composition: SpineDogfoodComposition, tmp_path):
    """Precondition: a synthetic tree with zero contract-marked tests (exit 5)."""
    return composition.make_test_tree(tmp_path, CollectScope.GENUINELY_EMPTY)


@when("the operator derives the contract gate-scope digest", target_fixture="gate_run")
def _when_derive_digest(composition: SpineDogfoodComposition, gate_repo):
    """Drive the real `run_contract_gate --collect-only --print-digest` CLI."""
    return composition.run_collect_only_digest(gate_repo)


@when(
    "the operator derives the contract gate-scope digest again",
    target_fixture="second_gate_run",
)
def _when_derive_digest_again(composition: SpineDogfoodComposition, gate_repo):
    """Drive the contract gate a second time over the unchanged tree (C4a)."""
    return composition.run_collect_only_digest(gate_repo)


@then("the digest fingerprints the real non-empty contract suite")
def _then_digest_fingerprints_real_suite(gate_run) -> None:
    assert gate_run.outcome is GuardOutcome.DIGEST_PRINTED, (
        "the contract gate did not print a digest -- slice-01 not delivered"
    )
    assert len(gate_run.digest) == 64, "digest is not a SHA-256 hex string"


@then("the digest is not the empty-suite sentinel")
def _then_digest_not_empty_sentinel(gate_run) -> None:
    assert gate_run.digest != EMPTY_DIGEST, (
        "digest is sha256('') -- the vacuous-gate defect is still present"
    )


@then("the collection that produced the digest preserved strict marker checking")
def _then_strict_markers_preserved(gate_run) -> None:
    assert gate_run.outcome is GuardOutcome.DIGEST_PRINTED, (
        "strict-markers-preserving collect did not succeed -- slice-01 "
        "not delivered (residuality S-1)"
    )


@then("both digest derivations produce the identical digest")
def _then_digest_is_idempotent(gate_run, second_gate_run) -> None:
    assert gate_run.digest == second_gate_run.digest != "", (
        "deriving the gate-scope digest twice over an unchanged suite "
        "produced different digests -- the digest is not deterministic"
    )


@then("the contract gate fails closed instead of digesting a partial scope")
def _then_gate_fails_closed(gate_run) -> None:
    # Exit-code-exact (BLOCKER 1): FAILED_CLOSED ⟺ exit 2 (the `_CollectionError`
    # path, DoD-2). DIGEST_PRINTED means the guard did not fire; UNEXPECTED means
    # it failed via a WRONG mode (exit 1/3/5, argparse, crash) -- both are caught.
    assert gate_run.outcome is GuardOutcome.FAILED_CLOSED, (
        f"expected fail-closed exit 2, got outcome {gate_run.outcome.value!r} "
        f"(exit {gate_run.exit_code}) -- "
        + (
            "the gate digested an untrustworthy collection (slice-01 guard not "
            "delivered)"
            if gate_run.outcome is GuardOutcome.DIGEST_PRINTED
            else "the gate failed via the WRONG mode -- not the DoD-2 "
            "`_CollectionError` -> exit 2 path"
        )
    )


@then("the operator is told the collection could not be trusted")
def _then_operator_told_untrustworthy(gate_run) -> None:
    assert "MalformedInput" in gate_run.stdout + gate_run.stderr, (
        "no MalformedInput event surfaced for the untrustworthy collection"
    )


@then("the contract gate digests the empty scope without failing closed")
def _then_empty_scope_digests_cleanly(gate_run) -> None:
    assert gate_run.outcome is GuardOutcome.DIGEST_PRINTED, (
        "a genuinely empty scope (exit 5) was wrongly failed closed -- the "
        "guard must distinguish exit 5 from a collection error"
    )


# ===========================================================================
# slice-02 -- a feature-end-cycle dispatch is accepted by the marker contract
# ===========================================================================


@given(
    parsers.parse("a crafter dispatch for phase {phase} scoped to {scope}"),
    target_fixture="dispatch",
)
def _given_crafter_dispatch(phase: str, scope: str) -> tuple[str, str]:
    """Precondition: a synthesised dispatch carrying a phase + a scope marker."""
    return (phase, scope)


@when("the marker contract classifies the dispatch", target_fixture="recognition")
def _when_classify_dispatch(
    composition: SpineDogfoodComposition, dispatch: tuple[str, str]
) -> DispatchRecognition:
    """Drive the real `classify_atdd_pure_dispatch` U0 domain chokepoint."""
    phase, scope = dispatch
    return composition.classify_dispatch(DispatchPhase(phase), DispatchScope(scope))


@then("the dispatch is recognised as valid")
def _then_dispatch_valid(recognition: DispatchRecognition) -> None:
    assert recognition is DispatchRecognition.VALID, (
        f"expected 'valid', got {recognition.value!r} -- the marker contract "
        "does not yet accept this dispatch (slice-02 not delivered)"
    )


@then("the dispatch is rejected as defective")
def _then_dispatch_defective(recognition: DispatchRecognition) -> None:
    assert recognition is DispatchRecognition.DEFECTIVE, (
        f"expected 'defective', got {recognition.value!r} -- the closed-world "
        "cross-field invariant is not enforced (slice-02 not delivered)"
    )
