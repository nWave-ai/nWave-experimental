"""Step definitions -- slice-03: methodology file-component detection.

F-DESIGN-REUSE-FIRST-GATE-CLI slice-03 (F-REUSE-GATE-COVER-METHODOLOGY-
COMPONENTS). DDD-8 / DDD-9 / DDD-10 / DDD-11.

slice-03 adds a SECOND detection unit alongside the slice-02 class-component
grep: an added file under a methodology-path kind (``nWave/data/**``,
``nWave/skills/**``, ``scripts/cli/**``) is ITSELF a NEW component keyed by its
repo-relative path/stem (DDD-10), NOT grepped for ``^class``. The two units
COMPOSE; ``new_components`` is the UNION (DDD-11). This closes the vacuous-PASS
blind spot where a new methodology SSOT artifact (e.g.
``nWave/data/dor-items.yaml``) ships unchallenged under the class-grep-only
detector.

Layer 3 (FS + subprocess acceptance) with a REAL driven adapter (real
filesystem + real ``git`` subprocess). Mandate 9 v2 OR-reduction: at least one
real driven adapter -> @real-io, example-based, ``assert_state_delta`` -- NO
PBT machinery. The verdict set (PASS / FAIL / preservation) is a finite
enumerable closed set -> example scenarios + a finite Scenario Outline over the
three methodology-path kinds, no ``@given``.

Step bodies delegate to ``ReuseFirstFixture``; no inline business logic
(Mandate-12 criterion 3) -- each body is a typed lookup plus a composition
call.

S1 (step-text uniqueness): every step literal here is slice-03-scoped --
distinct from the slice-02 literals (e.g. "NEW class" vs slice-02 "NEW
component", "...with methodology detection" vs slice-02 "...on the feature's
commit range"). No literal collides with another step file in this feature dir,
so pytest-bdd's global registry cannot shadow a slice-02 body. The Background
phrase is slice-03-specific for the same reason.

RED contract (Mandate 7): on master the production CLI has no
``--methodology-path`` flag and no file-component detection unit. Before the
slice-03 implementation lands:
  - AT1 (composition) commits a class (justified, detected by slice-02) AND a
    methodology file (justified, INVISIBLE to the class-grep). The slice-02
    detector reports new_components=1; AT1 asserts 2 -> assertion fires
    (MISSING_FUNCTIONALITY RED). Also ``--methodology-path`` is an unknown
    argparse flag -> SystemExit(2) -> UNRECOGNISED_INVOCATION -> the verdict /
    count assertions fire.
  - AT2 (the vacuous-PASS regression) commits a methodology file with NO Reuse
    Analysis row. Under slice-02 the file is invisible -> new_components=0 ->
    vacuous PASS; AT2 asserts FAIL -> assertion fires. (Once slice-03 lands the
    file-component is detected and unjustified -> real FAIL.)
  - AT3 (preservation) guards against fixture-theater: the structured-verdict
    Then step makes the scenario RED on master (no real CLI ran).
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
    METHODOLOGY_PATH_KIND_BY_PHRASE,
    VERDICT_BY_OUTCOME_PHRASE,
    BaseBranch,
    FeatureId,
    ReuseFirstVerdict,
)


scenarios("../slice-03-methodology-file-component-detection.feature")


# The canonical NEW class + methodology-file stem the slice-03 scenarios commit
# and (sometimes) name. The stem is the file-component key the lenient match
# (DDD-10) reads from the Reuse Analysis Existing Component column.
_NEW_CLASS = "WidgetService"
_NEW_METHODOLOGY_STEM = "dor-items"


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


@given("a feature with methodology paths whose source tree is tracked in a repository")
def given_repository_tracked(composition: ReuseFirstFixture) -> None:
    composition.create_feature(FeatureId("reuse-first-cli-demo"))
    composition.init_repository(BaseBranch("master"))


# --- Given -----------------------------------------------------------------


@given("the feature's commits add a NEW class to the source tree")
def given_commits_add_class(composition: ReuseFirstFixture) -> None:
    composition.commit_new_component(_NEW_CLASS, ADDED_PATH_KIND_BY_PHRASE["src"])


@given(
    parsers.parse(
        'the feature\'s commits add a NEW methodology file under "{methodology_path}"'
    )
)
def given_commits_add_methodology_file(
    composition: ReuseFirstFixture, methodology_path: str
) -> None:
    composition.commit_methodology_file(
        _NEW_METHODOLOGY_STEM, METHODOLOGY_PATH_KIND_BY_PHRASE[methodology_path]
    )


@given(
    "the feature names both the NEW class and the NEW methodology file "
    "in its Reuse Analysis section"
)
def given_reuse_analysis_names_both(composition: ReuseFirstFixture) -> None:
    composition.write_reuse_analysis_naming(named=[_NEW_CLASS, _NEW_METHODOLOGY_STEM])


@given(
    "the feature does not name that NEW methodology file in its Reuse Analysis section"
)
def given_reuse_analysis_omits_methodology_file(
    composition: ReuseFirstFixture,
) -> None:
    composition.write_reuse_analysis_naming(named=[])


@given(
    "the feature's commits add a NEW methodology file named in its Reuse Analysis section"
)
def given_commit_and_name_methodology_file(composition: ReuseFirstFixture) -> None:
    composition.commit_methodology_file(
        _NEW_METHODOLOGY_STEM, METHODOLOGY_PATH_KIND_BY_PHRASE["nWave/data"]
    )
    composition.write_reuse_analysis_naming(named=[_NEW_METHODOLOGY_STEM])


# --- When ------------------------------------------------------------------


@when(
    "the architect runs the reuse-first check on the feature's commit range "
    "with methodology detection"
)
def when_run_on_range_with_methodology(
    composition: ReuseFirstFixture, result_box: dict[str, object]
) -> None:
    result_box["universe_before"] = composition.capture_repo_universe()
    result_box["result"] = composition.run_check_on_range_with_methodology()


# --- Then ------------------------------------------------------------------


@then(
    parsers.parse(
        "the methodology-aware commit range {verdict_phrase} the reuse-first check"
    )
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
        f"stderr={result.stderr!r}) -- the methodology file-component unit "
        f"(DDD-8..DDD-11) is not yet implemented"
    )
    expected_exit = EXIT_CODE_BY_VERDICT[expected_verdict]
    assert result.exit_code == expected_exit, (
        f"expected exit code {expected_exit} for verdict "
        f"{expected_verdict.value}, got {result.exit_code}"
    )


@then(
    parsers.re(
        r"the methodology-aware reuse-first check reports "
        r"(?P<count_phrase>\w+) NEW components?"
    )
)
def then_reports_count(result_box: dict[str, object], count_phrase: str) -> None:
    result = result_box["result"]
    assert isinstance(result, CheckResult)
    expected = COMPONENT_COUNT_BY_PHRASE[count_phrase]
    assert result.new_component_count == expected, (
        f"expected {expected} NEW component(s), got {result.new_component_count} "
        f"(exit_code={result.exit_code}, stdout={result.stdout!r}, "
        f"stderr={result.stderr!r}) -- the union count (DDD-11) across "
        f"class-components and methodology file-components is wrong; the "
        f"file-component detection unit is not yet implemented"
    )


@then(
    "the reuse-first check with methodology detection produced a structured "
    "verdict for the commit range"
)
def then_structured_verdict_present(result_box: dict[str, object]) -> None:
    """Guards the preservation scenario against fixture-theater.

    On master the slice-03 file-component path does not exist (unknown
    ``--methodology-path`` flag -> SystemExit(2)), so
    ``run_check_on_range_with_methodology`` yields a synthetic
    UNRECOGNISED_INVOCATION result. The preservation assertion would otherwise
    pass vacuously (no CLI ran, no files mutated). This Then step makes the
    scenario fail-for-the-right-reason on master: the structured verdict is
    absent, the assertion fires, RED.
    """
    result = result_box["result"]
    assert isinstance(result, CheckResult)
    assert result.verdict is not ReuseFirstVerdict.UNRECOGNISED_INVOCATION, (
        f"reuse-first CLI did not produce a structured verdict on stdout "
        f"(exit_code={result.exit_code}, stdout={result.stdout!r}, "
        f"stderr={result.stderr!r}) -- the slice-03 methodology file-component "
        f"path is not yet implemented"
    )


@then(
    "the reuse-first check with methodology detection leaves the feature "
    "repository unchanged"
)
def then_repo_unchanged(
    composition: ReuseFirstFixture, result_box: dict[str, object]
) -> None:
    """Read-only contract over the real git repository (Mandate 8 / DDD-11).

    The universe is the feature-delta bytes + the committed HEAD sha + the
    working-tree porcelain status; all asserted ``unchanged`` so a real
    ``git diff`` invocation that accidentally staged, committed, or wrote a
    file (or read methodology-file bytes and rewrote them) would be caught.
    File-component detection reads diff PATHS only (DDD-11), so the repository
    is provably untouched.
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
