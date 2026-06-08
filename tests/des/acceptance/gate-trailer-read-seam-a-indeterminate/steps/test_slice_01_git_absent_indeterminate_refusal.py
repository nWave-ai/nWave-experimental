"""pytest-bdd binding: the commit-trailer verifier refuses LOUD when git is
absent or the SHA is unresolvable (slice-01 walking skeleton).

Driving port: the production ``des verify-commit-trailers`` CLI, invoked as a
subprocess black box (Mandate-13 driving-port-only, Layer 3 subprocess). Step
bodies delegate to the composition root (``composition.py``); no production
module is imported-and-called at the step boundary, and no business logic lives
in a step body (Mandate-12 criterion 3: each body is a single delegation).

The ``scenarios(...)`` call binds every scenario in the ``.feature`` file via
the RELATIVE path from this steps/ module -- the proven-collecting form used by
the sibling suite gate-trailer-read-git-port-extract. This routes the scenario
@tags through pytest-bdd's tag-to-dynamic-mark pipeline, which the project's
filterwarnings makes --strict-markers-safe. Each step decorator's literal text
is unique within this feature directory (S1 step-text-uniqueness invariant).

RED scaffold (empirically confirmed at authorship HEAD):
  * GIT_BINARY_ABSENT scenario: FileNotFoundError propagates uncaught from
    subprocess.run at line 132 of verify_commit_trailers.py -> Python emits a
    raw traceback to stderr and exits with code 1. The Then-step asserts
    exit 7 + a structured reason on stderr -> fails with AssertionError (wrong
    exit code, raw traceback present).
  * SHA_UNRESOLVABLE scenario: RuntimeError caught at line 181-183 -> exit 6.
    The Then-step asserts exit 7 -> fails with AssertionError (got exit 6, the
    malformed-trailer code -- wrong severity class).
  * REAL_WORK_TREE_SIGNED scenario (parity control): already exits 0 at HEAD
    for a correctly signed commit -> this scenario is GREEN-on-author (expected;
    it proves the seam-A re-point does not regress the happy path).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition import TrailerVerifierComposition


scenarios("../slice-01-git-absent-indeterminate-refusal.feature")


@pytest.fixture
def composition() -> Iterator[TrailerVerifierComposition]:
    comp = TrailerVerifierComposition()
    yield comp
    comp.cleanup()


# --- Given -------------------------------------------------------------------


@given("a target directory without the git binary available")
def given_git_binary_absent(composition: TrailerVerifierComposition) -> None:
    composition.given_git_binary_absent()


@given("a git work-tree where the requested commit SHA does not exist")
def given_unresolvable_sha(composition: TrailerVerifierComposition) -> None:
    composition.given_unresolvable_sha_in_work_tree()


@given("a real git work-tree with a commit carrying a correctly signed trailer")
def given_signed_commit(composition: TrailerVerifierComposition) -> None:
    composition.given_real_work_tree_with_signed_commit()


# --- When --------------------------------------------------------------------


@when("the operator runs des verify-commit-trailers on a commit in that directory")
def when_runs_verifier_git_absent(composition: TrailerVerifierComposition) -> None:
    composition.when_operator_runs_verifier()


@when("the operator runs des verify-commit-trailers on that unresolvable SHA")
def when_runs_verifier_unresolvable(composition: TrailerVerifierComposition) -> None:
    composition.when_operator_runs_verifier()


@when("the operator runs des verify-commit-trailers on that signed commit")
def when_runs_verifier_signed(composition: TrailerVerifierComposition) -> None:
    composition.when_operator_runs_verifier()


# --- Then --------------------------------------------------------------------


@then("the verifier refuses with a loud cannot-evaluate verdict")
def then_refuses_loud(composition: TrailerVerifierComposition) -> None:
    composition.then_refuses_with_loud_cannot_evaluate()


@then("the cannot-evaluate verdict names a reason on standard error")
def then_names_reason(composition: TrailerVerifierComposition) -> None:
    composition.then_cannot_evaluate_names_reason()


@then("the verifier does not emit a raw Python stack-trace")
def then_no_stack_trace(composition: TrailerVerifierComposition) -> None:
    composition.then_no_raw_stack_trace()


@then("the verifier does not mutate the target directory")
def then_pure_read(composition: TrailerVerifierComposition) -> None:
    composition.then_does_not_mutate_target_directory()


@then("the cannot-evaluate verdict is distinct from the tampering verdict")
def then_distinct_from_tampering(composition: TrailerVerifierComposition) -> None:
    composition.then_cannot_evaluate_distinct_from_tampering()


@then("the cannot-evaluate verdict is distinct from the malformed-trailer verdict")
def then_distinct_from_malformed(composition: TrailerVerifierComposition) -> None:
    composition.then_cannot_evaluate_distinct_from_malformed()


@then("the verifier produces the verified verdict")
def then_verified(composition: TrailerVerifierComposition) -> None:
    composition.then_verifier_produces_verified_verdict()
