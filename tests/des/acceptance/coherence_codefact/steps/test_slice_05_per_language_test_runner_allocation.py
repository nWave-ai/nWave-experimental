"""pytest-bdd binding for the f-coherence-and-attestation slice-05 scenarios.

Driving surface (Mandate-13 driving-port-only):
  * AT-16 / AT-17 -> Layer 3 composition: the REAL per-language TestRunnerPort
    resolution registry (resolve(target_root) -> RunnerAdapter | Indeterminate)
    over a REAL tmp_path target carrying a real lockfile.
  * AT-18 -> Layer 3 subprocess: the REAL `des run-contract-gate` scoped to one
    slice (which tests RAN -- the §V.B ATs@slice allocation).
  * AT-19 -> Layer 3 composition: the REAL feature-end full-suite leg +
    removal-of-obsolete (the discriminating whole-tree marker's absence on the
    shipped slice-gate surface).

Step bodies delegate to the composition root (composition_slice_05_test_runner.py);
no business logic in step bodies (Mandate-12). The <lockfile>/<runner> tokens are
parsed once into the typed RECOGNIZED_BY_FILENAME / TargetRunner vocabulary, so
ONE Scenario-Outline shape ranges over the LOCKED (lockfile -> runner) map.

active-RED scaffold (atdd_pure -- NOT @skip): every scenario is RED until DELIVER
lands the slice-05 seams (the runner port + the slice-AT RUN re-scope + the
feature-end full-suite leg / C10 removal). Each scenario fails with a semantic
AssertionError naming the missing seam, never a collection / import / setup error.

STEP-TEXT UNIQUENESS (S1): every literal/template step phrase below is DISTINCT
from the slice-01 + slice-02 + slice-03 + slice-04 step phrases. slice-01 uses
"is asked for the fact through the CodeFactPort"; slice-02 "answers the structural
fact" / "negotiates the best available provider"; slice-03 "diffs the design
contract against the acceptance tests"; slice-04 "the self-attest layer classifies
the gate verdict" / "a gate verdict that is ...". slice-05 uses "the test-runner
port resolves the runner for the target" / "a target project carrying a ..." /
"the contract gate runs scoped to the entering slice" / "the feature-end
allocation is inspected" -- no pytest-bdd global-registry shadow.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_05_test_runner import RunnerAllocationComposition
from .domain_types_slice_05_test_runner import TargetRunner


scenarios("../slice-05-per-language-test-runner-allocation.feature")


# Runner wire-token (kebab/lowercase) -> typed TargetRunner.
_RUNNER_BY_TOKEN = {runner.value: runner for runner in TargetRunner}


@pytest.fixture
def test_runner() -> RunnerAllocationComposition:
    return RunnerAllocationComposition()


# --- Given -----------------------------------------------------------------


@given(parsers.parse("a target project carrying a {lockfile} build manifest"))
def given_target_with_lockfile(
    test_runner: RunnerAllocationComposition, tmp_path: Path, lockfile: str
) -> None:
    test_runner.given_target_with_lockfile(tmp_path, lockfile)


@given("a target project carrying an unrecognized build manifest")
def given_target_with_unrecognized_manifest(
    test_runner: RunnerAllocationComposition, tmp_path: Path
) -> None:
    test_runner.given_target_with_unrecognized_lockfile(tmp_path)


@given("a target repository entering a single slice")
def given_repo_entering_slice(
    test_runner: RunnerAllocationComposition, tmp_path: Path
) -> None:
    test_runner.given_repo_entering_slice(tmp_path, "slice-01")


@given("a feature reaching its feature-end cycle")
def given_feature_reaching_feature_end(
    test_runner: RunnerAllocationComposition,
) -> None:
    # The feature-end full-suite leg is a shipped-surface property -- no extra
    # arming needed; the When reads the REAL cycle surface.
    pass


# --- When ------------------------------------------------------------------


@when("the test-runner port resolves the runner for the target")
def when_resolving_the_runner(test_runner: RunnerAllocationComposition) -> None:
    test_runner.when_resolving_the_runner()


@when("the contract gate runs scoped to the entering slice")
def when_slice_gate_runs(test_runner: RunnerAllocationComposition) -> None:
    test_runner.when_slice_gate_runs()


@when("the feature-end allocation is inspected")
def when_inspecting_feature_end_allocation(
    test_runner: RunnerAllocationComposition,
) -> None:
    test_runner.when_inspecting_feature_end_allocation()


# --- Then ------------------------------------------------------------------


@then(parsers.parse("the test-runner port resolves the {runner} test runner"))
def then_resolved_runner_is(
    test_runner: RunnerAllocationComposition, runner: str
) -> None:
    test_runner.then_resolved_runner_is(_RUNNER_BY_TOKEN[runner])


@then("the test-runner port degrades loud to an indeterminate verdict")
def then_resolution_is_indeterminate(test_runner: RunnerAllocationComposition) -> None:
    test_runner.then_resolution_is_indeterminate()


@then("the test-runner port does not silently fall back to the pytest runner")
def then_resolution_does_not_fall_back_to_pytest(
    test_runner: RunnerAllocationComposition,
) -> None:
    test_runner.then_resolution_does_not_fall_back_to_pytest()


@then("the contract gate runs only the entering slice's acceptance tests")
def then_slice_gate_runs_slice_ats_only(
    test_runner: RunnerAllocationComposition,
) -> None:
    test_runner.then_slice_gate_runs_slice_ats_only()


@then("the contract gate does not run the whole tree")
def then_slice_gate_does_not_run_whole_tree(
    test_runner: RunnerAllocationComposition,
) -> None:
    # The whole-tree-absence assertion is folded into the slice-scope reader
    # (then_slice_gate_runs_slice_ats_only asserts ran_whole_tree is False); this
    # step re-affirms the same observable so the Gherkin reads as a narrative.
    test_runner.then_slice_gate_runs_slice_ats_only()


@then("a distinct full suite runs once at feature-end")
def then_feature_end_runs_full_suite_once(
    test_runner: RunnerAllocationComposition,
) -> None:
    test_runner.then_feature_end_runs_full_suite_once()


@then("the obsolete whole-tree run at every commit-slice is removed")
def then_obsolete_whole_tree_at_slice_is_removed(
    test_runner: RunnerAllocationComposition,
) -> None:
    test_runner.then_obsolete_whole_tree_at_slice_is_removed()
