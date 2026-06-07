"""Step definitions -- slice-01: pytest warnings filter for PytestUnknownMarkWarning.

F-FIX-CICD-WARNING-SUPPRESS slice-01. Layer 3 (subprocess + FS acceptance):
the production fix surface is the
`[tool.pytest.ini_options].filterwarnings` entry in `pyproject.toml`; the
SUT is the real `pipenv run pytest <known-noisy-file> --collect-only -q`
subprocess that consumes that configuration at startup.

The only driven ports are:
  - the real subprocess (`pipenv run pytest <file> --collect-only -q`),
  - the real filesystem (the known-noisy file at
    tests/installer/acceptance/atdd-spine-ledger-enforcement-gate-v2/
    steps/test_slice_02_pre_tool_use_hook.py),
  - the real pyproject.toml (the production fix lives there; the SUT
    reads it implicitly via pytest's own startup).

Example-based (Mandate 11 -- layer 3 sad paths enumerated explicitly).
Two ATs cover the slice-01 contract: walking-skeleton absent-warnings +
stdout volume reduction. PBT precluded by OR-reduction (Mandate 9 v2:
real I/O on `pipenv run pytest` subprocess + real filesystem read).

Step bodies delegate to `WarningFilterFixture` (Mandate-12 criterion 3:
<=2 statements per body, final statement is a composition method call,
zero control flow in step bodies).

RED-for-the-right-reason: the production fix
(`pyproject.toml[tool.pytest.ini_options].filterwarnings` suppressing
`PytestUnknownMarkWarning`) does NOT EXIST YET (the crafter lands it in
DELIVER per the feature-delta `Wave: DELIVER (pending)` ordering). When
the composition fixture invokes the real pytest subprocess, the captured
combined output contains 9 `PytestUnknownMarkWarning` occurrences (and 46
total lines) on the slice-02 target file. The AT then fires AssertionError
on the first `Then` step (`assert_zero_unknown_mark_warnings_in_output`
for AT-1; `assert_output_volume_reduction_at_least_eighty_percent_vs_baseline`
for AT-2). That is the correct RED: the assertion fires because the
warnings filter is unimplemented, not because of an import error or
fixture setup bug.

Mandate-13 (driving-port-only): every step delegates to the composition
fixture, which drives the SUT via `pipenv run pytest <file>
--collect-only -q` subprocess. ZERO direct production imports in step
composition. ZERO function-boundary invocation of production modules
(the production "module" here is the pyproject.toml configuration entry;
it is consumed by the real pytest startup, not imported in step bodies).

Skip-marker contract (ADR-028 + friction #26 lesson): this module carries
`pytestmark = pytest.mark.skip(reason="DISTILL scaffold; crafter unskips
on A_GREEN_ATS")` at FILE HEAD. The crafter unskips on the A_GREEN_ATS
spine phase after the DELIVER production fix lands.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition import PytestRunCapture, WarningFilterFixture


# Skip marker REMOVED on A_GREEN_ATS (2026-05-28) — the production fix
# pyproject.toml[tool.pytest.ini_options].filterwarnings = [
#     "ignore::pytest.PytestUnknownMarkWarning",
# ]
# now suppresses the PytestUnknownMarkWarning class for pytest-bdd dynamic
# marks. AT-1 (zero warnings) + AT-2 (≤15 lines) GREEN.


scenarios("../slice-01-pytest-warning-filter.feature")


# --- Fixtures --------------------------------------------------------------


@pytest.fixture
def fixture(tmp_path: Path) -> WarningFilterFixture:
    """Per-test warning-filter fixture rooted at an isolated tmp workspace."""
    return WarningFilterFixture(target_root=tmp_path / "workspace")


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for the captured PytestRunCapture across When/Then steps."""
    return {}


# --- Background ------------------------------------------------------------


@given(
    'the repository carries pytest-bdd acceptance tests under "tests/installer/acceptance/"'
)
def given_repo_carries_acceptance_tests(fixture: WarningFilterFixture) -> None:
    fixture.assert_known_noisy_file_exists()


@given(
    'the project\'s known custom mark namespace includes "@slice-NN", "@walking_skeleton", '
    '"@driving_port", "@real-io", "@contract-shape:*", "@feature-*", "@e2e_smoke", '
    '"@fast-path", "@matcher-collision-spike", "@coupled", "@infrastructure", '
    '"@partial-failure-tolerance"'
)
def given_known_custom_mark_namespace(fixture: WarningFilterFixture) -> None:
    fixture.acknowledge_known_custom_mark_namespace()


@given(
    'pytest-bdd auto-converts each Gherkin tag on a scenario into a "pytest.mark.<tag>" '
    "object at collection time"
)
def given_pytest_bdd_tag_conversion(fixture: WarningFilterFixture) -> None:
    fixture.acknowledge_pytest_bdd_tag_conversion()


# --- Shared preconditions --------------------------------------------------


@given(
    "a known-noisy pytest-bdd test file at "
    '"tests/installer/acceptance/atdd-spine-ledger-enforcement-gate-v2/steps/'
    'test_slice_02_pre_tool_use_hook.py" whose scenarios carry tags from the known '
    "custom mark namespace"
)
def given_known_noisy_file(fixture: WarningFilterFixture) -> None:
    fixture.assert_known_noisy_file_exists()


@given(
    'the project\'s "pyproject.toml" declares a pytest warnings filter that suppresses '
    '"PytestUnknownMarkWarning" for the known custom mark namespace'
)
def given_pyproject_declares_filter(fixture: WarningFilterFixture) -> None:
    fixture.acknowledge_production_filter_declared_in_pyproject()


# --- Shared action --------------------------------------------------------


@when(
    "the developer runs the pytest collection command "
    '"pipenv run pytest <known-noisy-file> --collect-only -q"'
)
def when_developer_runs_pytest_collect_only(
    fixture: WarningFilterFixture, result_box: dict[str, object]
) -> None:
    result_box["capture"] = fixture.run_collect_only_on_known_noisy_file()


# --- AT-1 observations (absent-warnings contract) -------------------------


@then(
    "the captured combined output contains ZERO occurrences of the substring "
    '"PytestUnknownMarkWarning"'
)
def then_zero_unknown_mark_warnings(
    fixture: WarningFilterFixture, result_box: dict[str, object]
) -> None:
    capture: PytestRunCapture = result_box["capture"]  # type: ignore[assignment]
    fixture.assert_zero_unknown_mark_warnings_in_output(capture)


@then("the pytest exit code is zero")
def then_pytest_exit_code_zero(
    fixture: WarningFilterFixture, result_box: dict[str, object]
) -> None:
    capture: PytestRunCapture = result_box["capture"]  # type: ignore[assignment]
    fixture.assert_pytest_exit_code_zero(capture)


@then(
    'no warning of class "PytestUnknownMarkWarning" is surfaced for any tag in the known '
    "custom mark namespace"
)
def then_no_per_tag_warning_for_namespace(
    fixture: WarningFilterFixture, result_box: dict[str, object]
) -> None:
    capture: PytestRunCapture = result_box["capture"]  # type: ignore[assignment]
    fixture.assert_no_warning_surfaced_for_known_namespace(capture)


# --- AT-2 observations (bounded-output-size contract) ---------------------


@then(
    "the captured combined output line count is at most 20% of the pre-fix baseline "
    "line count for the same command on the same file"
)
def then_line_count_at_most_twenty_percent_of_baseline(
    fixture: WarningFilterFixture, result_box: dict[str, object]
) -> None:
    capture: PytestRunCapture = result_box["capture"]  # type: ignore[assignment]
    fixture.assert_output_volume_reduction_at_least_eighty_percent_vs_baseline(capture)


@then("the captured combined output line count is at most 15 lines")
def then_line_count_at_most_fifteen(
    fixture: WarningFilterFixture, result_box: dict[str, object]
) -> None:
    capture: PytestRunCapture = result_box["capture"]  # type: ignore[assignment]
    fixture.assert_output_line_count_at_most_fifteen(capture)
