"""Step definitions -- slice-02: real git-diff-driven NEW component detection.

F-DESIGN-REUSE-FIRST-GATE-CLI slice-02 (real git-diff CORE). DDD-3 / DDD-6 /
DDD-7.

slice-02 promotes the detector from the slice-01 fixture-injected name list to
the feature's REAL commit range: the CLI runs ``git diff --name-status
master...HEAD`` against a real repository under tmp_path and greps the added
``src/**`` files for ``^class <Name>(`` declarations. The trunk (master) and the
scoped source tree (src) are the conventional hard-coded defaults; making them
overridable via ``--base-branch`` / ``--scoped-path`` is deferred to slice-04
(PARKED off the collection path under
``docs/feature/fix-design-reuse-first-gate-cli/distill/pending-slices/``).

Layer 3 (FS + subprocess acceptance) with a REAL driven adapter (real
filesystem + real ``git`` subprocess). Mandate 9 v2 OR-reduction: at least one
real driven adapter -> @real-io, example-based, ``assert_state_delta`` -- NO
PBT machinery. The verdict set (PASS / FAIL / preservation) is a finite
enumerable closed set -> example scenarios, no ``@given``.

Step bodies delegate to ``ReuseFirstFixture``; no inline business logic
(Mandate-12 criterion 3) -- each body is a typed lookup plus a composition
call.

RED contract (Mandate 7): on master the production CLI does not run a real git
diff (it requires ``--git-diff-source=path:<file>``). The crafter authors the
RED scaffold + slice-02 implementation in A_GREEN_ATS. Before the
implementation lands, ``composition.run_check_on_range`` defends the import +
argparse boundary so the @then assertion fires (RED-for-the-right-reason at the
AT layer) rather than a collection-time error; once the real-git path lands the
path is the real stdout token -> PASS / FAIL.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .composition import CheckResult, ReuseFirstFixture
from .domain_types import (
    ADDED_PATH_KIND_BY_PHRASE,
    COMPONENT_COUNT_BY_PHRASE,
    EXIT_CODE_BY_VERDICT,
    VERDICT_BY_OUTCOME_PHRASE,
    BaseBranch,
    FeatureId,
    ReuseFirstVerdict,
)


scenarios("../slice-02-real-git-diff-detection.feature")


# The canonical NEW class the slice-02 scenarios commit + (sometimes) name.
_NEW_COMPONENT = "WidgetService"


# --- Fixtures --------------------------------------------------------------


@pytest.fixture
def composition(tmp_path: Path) -> ReuseFirstFixture:
    """Production-wired composition root over a real tmp_path git repository."""
    return ReuseFirstFixture(repo_dir=tmp_path / "repo")


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for the CLI result + universe across When -> Then steps."""
    return {}


# --- Background -------------------------------------------------------------


@given("a feature whose source tree is tracked in a repository")
def given_repository_tracked(composition: ReuseFirstFixture) -> None:
    composition.create_feature(FeatureId("reuse-first-cli-demo"))
    composition.init_repository(BaseBranch("master"))


# --- Given -----------------------------------------------------------------


@given("the feature's commits add a NEW component to the source tree")
def given_commits_add_component(composition: ReuseFirstFixture) -> None:
    composition.commit_new_component(_NEW_COMPONENT, ADDED_PATH_KIND_BY_PHRASE["src"])


@given("the feature names that NEW component in its Reuse Analysis section")
def given_reuse_analysis_names_component(composition: ReuseFirstFixture) -> None:
    composition.write_reuse_analysis(naming=_NEW_COMPONENT)


@given("the feature does not name that NEW component in its Reuse Analysis section")
def given_reuse_analysis_omits_component(composition: ReuseFirstFixture) -> None:
    composition.write_reuse_analysis(naming=None)


@given("the feature's commits add a NEW component named in its Reuse Analysis section")
def given_commit_and_name_component(composition: ReuseFirstFixture) -> None:
    composition.commit_new_component(_NEW_COMPONENT, ADDED_PATH_KIND_BY_PHRASE["src"])
    composition.write_reuse_analysis(naming=_NEW_COMPONENT)


# --- When ------------------------------------------------------------------


@when("the architect runs the reuse-first check on the feature's commit range")
def when_run_on_range(
    composition: ReuseFirstFixture, result_box: dict[str, object]
) -> None:
    result_box["universe_before"] = composition.capture_repo_universe()
    result_box["result"] = composition.run_check_on_range()


# --- Then ------------------------------------------------------------------


@then(
    parsers.parse("the feature's commit range {verdict_phrase} the reuse-first check")
)
def then_commit_range_verdict(
    result_box: dict[str, object], verdict_phrase: str
) -> None:
    result = result_box["result"]
    assert isinstance(result, CheckResult)
    expected_verdict = VERDICT_BY_OUTCOME_PHRASE[verdict_phrase]
    assert result.verdict is expected_verdict, (
        f"expected verdict {expected_verdict.value}, got {result.verdict.value} "
        f"(exit_code={result.exit_code}, stdout={result.stdout!r}, "
        f"stderr={result.stderr!r})"
    )
    expected_exit = EXIT_CODE_BY_VERDICT[expected_verdict]
    assert result.exit_code == expected_exit, (
        f"expected exit code {expected_exit} for verdict "
        f"{expected_verdict.value}, got {result.exit_code}"
    )


@then(parsers.parse("the reuse-first check reports {count_phrase} NEW component"))
def then_reports_count(result_box: dict[str, object], count_phrase: str) -> None:
    result = result_box["result"]
    assert isinstance(result, CheckResult)
    expected = COMPONENT_COUNT_BY_PHRASE[count_phrase]
    assert result.new_component_count == expected, (
        f"expected {expected} NEW component(s), got {result.new_component_count} "
        f"(exit_code={result.exit_code}, stdout={result.stdout!r}, "
        f"stderr={result.stderr!r}) -- the real git-diff detector did not "
        f"report the expected commit-range component cardinality"
    )


@then("the reuse-first check produced a structured verdict for the commit range")
def then_structured_verdict_present(result_box: dict[str, object]) -> None:
    """Guards the preservation scenario against fixture-theater.

    On master the real-git path does not exist, so ``run_check_on_range``
    yields a synthetic UNRECOGNISED_INVOCATION result. The preservation
    assertion would otherwise pass vacuously (no CLI ran, no files mutated).
    This Then step makes the scenario fail-for-the-right-reason on master: the
    structured verdict is absent, the assertion fires, RED.
    """
    result = result_box["result"]
    assert isinstance(result, CheckResult)
    assert result.verdict is not ReuseFirstVerdict.UNRECOGNISED_INVOCATION, (
        f"reuse-first CLI did not produce a structured verdict on stdout "
        f"(exit_code={result.exit_code}, stdout={result.stdout!r}, "
        f"stderr={result.stderr!r}) -- the slice-02 real-git-diff path is not "
        f"yet implemented"
    )


@then("the reuse-first check leaves the feature repository unchanged")
def then_repo_unchanged(
    composition: ReuseFirstFixture, result_box: dict[str, object]
) -> None:
    """Read-only contract over the real git repository (Mandate 8 / DDD-3).

    The universe is the feature-delta bytes + the committed HEAD sha + the
    working-tree porcelain status; all asserted ``unchanged`` so a real
    ``git diff`` invocation that accidentally staged, committed, or wrote a
    file would be caught.
    """
    assert_state_delta(
        before=result_box["universe_before"],  # type: ignore[arg-type]
        after=composition.capture_repo_universe(),
        universe={
            "feature_delta.bytes",
            "repo.head_sha",
            "repo.porcelain_status",
        },
        expected={
            "feature_delta.bytes": unchanged(),
            "repo.head_sha": unchanged(),
            "repo.porcelain_status": unchanged(),
        },
    )
