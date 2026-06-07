"""Step definitions -- slice-06: methodology-path default-wiring closure.

F-DESIGN-REUSE-FIRST-GATE-CLI slice-06. DDD-9 (default methodology-path set) /
DDD-11 (union verdict).

slice-03 added the file-component detection unit; slice-05 extended the
nw-design skill prose to promise the architect that the CLI DEFAULTS to the
published-language methodology paths (``nWave/data``, ``nWave/skills``,
``scripts/cli``). The impl, however, wires ``--methodology-path`` with
``default=None`` -> file-component detection is DEFAULT-OFF -> a caller who
OMITS the flag gets a vacuous PASS where a NEW methodology SSOT artifact ships
unchallenged. slice-06 pins the no-flag default-on contract: an added
methodology file under a published-language path, absent from the Reuse
Analysis, is rejected EVEN WHEN ``--methodology-path`` is omitted.

Layer 3 (FS + subprocess acceptance) with a REAL driven adapter (real
filesystem + real ``git`` subprocess). Mandate 9 v2 OR-reduction: at least one
real driven adapter -> @real-io, example-based, ``assert_state_delta`` -- NO
PBT machinery. The verdict set (FAIL / preservation) is finite enumerable
closed -> a single example scenario, no ``@given``.

Step bodies delegate to ``ReuseFirstFixture``; no inline business logic
(Mandate-12 criterion 3) -- each body is a typed lookup plus a composition
call.

S1 (step-text uniqueness): every step literal here is slice-06-scoped via the
"default-wired" / "without the methodology-path flag" phrasing -- distinct from
the slice-03 literals ("...with methodology detection") so pytest-bdd's global
step registry cannot shadow a slice-03 body. The Background phrase is
slice-06-specific for the same reason.

RED contract (Mandate 7): on master the production CLI resolves
``methodology_paths = args.methodology_paths or []`` with ``default=None``, then
guards ``if methodology_paths and args.git_diff_source is None`` -> with NO
``--methodology-path`` flag ``methodology_paths`` is ``[]`` -> the guard is
False -> ``file_components = []`` -> the committed ``nWave/data`` file is
INVISIBLE -> ``new_components=0`` -> vacuous ``verdict=PASS`` / exit 0. This AT
asserts FAIL / exit 1 / one NEW component, so on master:
  - ``then_default_wired_verdict`` fires (verdict PASS != FAIL,
    exit 0 != 1) -- the default-off deviation surfaced as a semantic
    ``AssertionError`` (MISSING_FUNCTIONALITY RED), NOT a collection/import
    error. GREEN wires the three published-language paths ON by default.
  - ``then_default_wired_reports_count`` fires (0 != 1).
  - ``then_default_wired_repo_unchanged`` (preservation) stays GREEN under both
    states -- the CLI is read-only regardless of the default-wiring.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .composition import CheckResult, ReuseFirstFixture
from .domain_types import (
    COMPONENT_COUNT_BY_PHRASE,
    EXIT_CODE_BY_VERDICT,
    METHODOLOGY_PATH_KIND_BY_PHRASE,
    VERDICT_BY_OUTCOME_PHRASE,
    BaseBranch,
    FeatureId,
)


scenarios("../slice-06-methodology-path-default-wiring.feature")


# The canonical methodology-file stem the slice-06 scenario commits but does NOT
# name in the Reuse Analysis. The stem is the file-component key the lenient
# match (DDD-10) reads from the Existing Component column.
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


@given(
    "a feature whose methodology source tree is tracked in a default-wired repository"
)
def given_default_wired_repository(composition: ReuseFirstFixture) -> None:
    composition.create_feature(FeatureId("reuse-first-cli-demo"))
    composition.init_repository(BaseBranch("master"))


# --- Given -----------------------------------------------------------------


@given(
    parsers.parse(
        "the feature's commits add a NEW methodology file under "
        '"{methodology_path}" to the default-wired repository'
    )
)
def given_default_wired_commits_methodology_file(
    composition: ReuseFirstFixture, methodology_path: str
) -> None:
    composition.commit_methodology_file(
        _NEW_METHODOLOGY_STEM, METHODOLOGY_PATH_KIND_BY_PHRASE[methodology_path]
    )


@given(
    "the default-wired feature does not name that NEW methodology file "
    "in its Reuse Analysis section"
)
def given_default_wired_reuse_analysis_omits_file(
    composition: ReuseFirstFixture,
) -> None:
    composition.write_reuse_analysis_naming(named=[])


# --- When ------------------------------------------------------------------


@when(
    "the architect runs the reuse-first check on the feature's commit range "
    "without the methodology-path flag"
)
def when_run_on_range_without_methodology_flag(
    composition: ReuseFirstFixture, result_box: dict[str, object]
) -> None:
    result_box["universe_before"] = composition.capture_repo_universe()
    result_box["result"] = composition.run_check_on_range_without_methodology_flag()


# --- Then ------------------------------------------------------------------


@then(
    parsers.parse(
        "the default-wired commit range {verdict_phrase} the reuse-first check"
    )
)
def then_default_wired_verdict(
    result_box: dict[str, object], verdict_phrase: str
) -> None:
    result = result_box["result"]
    assert isinstance(result, CheckResult)
    expected_verdict = VERDICT_BY_OUTCOME_PHRASE[verdict_phrase]
    assert result.verdict is expected_verdict, (
        f"expected verdict {expected_verdict.value}, got {result.verdict.value} "
        f"(exit_code={result.exit_code}, stdout={result.stdout!r}, "
        f"stderr={result.stderr!r}) -- the methodology-path default set "
        f"(DDD-9) is not wired: without --methodology-path the impl resolves "
        f"methodology_paths=[] -> file detection OFF -> vacuous PASS"
    )
    expected_exit = EXIT_CODE_BY_VERDICT[expected_verdict]
    assert result.exit_code == expected_exit, (
        f"expected exit code {expected_exit} for verdict "
        f"{expected_verdict.value}, got {result.exit_code}"
    )


@then(
    parsers.re(
        r"the default-wired reuse-first check reports "
        r"(?P<count_phrase>\w+) NEW components?"
    )
)
def then_default_wired_reports_count(
    result_box: dict[str, object], count_phrase: str
) -> None:
    result = result_box["result"]
    assert isinstance(result, CheckResult)
    expected = COMPONENT_COUNT_BY_PHRASE[count_phrase]
    assert result.new_component_count == expected, (
        f"expected {expected} NEW component(s), got {result.new_component_count} "
        f"(exit_code={result.exit_code}, stdout={result.stdout!r}, "
        f"stderr={result.stderr!r}) -- without --methodology-path the default "
        f"published-language set (nWave/data, nWave/skills, scripts/cli) must "
        f"still detect the committed methodology file-component (DDD-9 default)"
    )


@then(
    "the reuse-first check without the methodology-path flag leaves the "
    "feature repository unchanged"
)
def then_default_wired_repo_unchanged(
    composition: ReuseFirstFixture, result_box: dict[str, object]
) -> None:
    """Read-only contract over the real git repository (Mandate 8 / DDD-11).

    The universe is the feature-delta bytes + the committed HEAD sha + the
    working-tree porcelain status; all asserted ``unchanged`` so a real
    ``git diff`` invocation that accidentally staged, committed, or wrote a file
    would be caught. The default-wiring change reads diff PATHS only (DDD-11),
    so the repository is provably untouched whether the flag is present or not.
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
