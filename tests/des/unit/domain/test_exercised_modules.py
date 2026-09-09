"""What a pytest run IMPORTED of the subject's product code, as a measurement.

MEASURED (run 34, 2026-09-06 03:45; same class run 27).  The examiner refused
candidate 6a8e46cde because "the other two causes are only exercised inside
pytest runs of test modules whose touches_test_paths is true", and the
orchestrator then verified the three causes by hand against the real root and
integrated.  The oracle it rejected drives `des.cli.code_fact.main` in-process:
it EXERCISES the product.  `touches_test_paths` is true for every pytest argv,
so it cannot tell a test that drives the product from run 24's test that drove
a stand-in -- one bit caught run 24 and rejected run 34.

This module measures the fact that was missing, and decides nothing with it
(`boundary:software-measures-model-decides`, GDP-8: the property, which product
files the run imported, never the designation of the argv's paths).
"""

from __future__ import annotations

from des.domain.exercised_modules import (
    INDETERMINATE,
    MEASURED,
    NOT_APPLICABLE,
    exercised_modules,
    invokes_pytest,
)


ROOT = "/tmp/candidate"
TEST_PATHS = ("tests",)


def report(*paths: str) -> str:
    return "\n".join(paths)


def test_a_pytest_run_importing_a_product_module_names_it() -> None:
    """(i) A test that drives `src/` -- the run-34 shape, now visible."""
    measured = exercised_modules(
        ("python", "-m", "pytest", "tests/unit/test_code_fact.py", "-q"),
        report(f"{ROOT}/src/des/cli/code_fact.py", "/usr/lib/python3.12/json.py"),
        ROOT,
        TEST_PATHS,
        ("src/des/cli/code_fact.py",),
    )

    assert measured.measure == MEASURED
    assert measured.paths == ("src/des/cli/code_fact.py",)
    assert measured.changed_targets == ("src/des/cli/code_fact.py",)


def test_a_pytest_run_driving_only_a_stand_in_names_no_product_module() -> None:
    """(ii) Run 24's shape: the fixture answered, no product byte was imported."""
    measured = exercised_modules(
        ("python", "-m", "pytest", "tests/acceptance", "-q"),
        report(f"{ROOT}/tests/acceptance/support.py", f"{ROOT}/tests/conftest.py"),
        ROOT,
        TEST_PATHS,
        ("src/product/value.py",),
    )

    assert measured.measure == MEASURED
    assert measured.paths == ()
    assert measured.changed_targets == ()


def test_a_changed_product_file_the_run_never_imported_is_not_a_target() -> None:
    """The intersection is measured, not assumed: exercised is not changed."""
    measured = exercised_modules(
        ("pytest", "tests"),
        report(f"{ROOT}/src/des/cli/code_fact.py"),
        ROOT,
        TEST_PATHS,
        ("src/des/domain/other.py",),
    )

    assert measured.paths == ("src/des/cli/code_fact.py",)
    assert measured.changed_targets == ()


def test_a_pytest_argv_whose_session_wrote_nothing_is_indeterminate() -> None:
    """(iii) LOUD, never a silent empty list: pytest never reached the finish."""
    measured = exercised_modules(("pytest", "tests"), None, ROOT, TEST_PATHS, ())

    assert measured.measure == INDETERMINATE
    assert measured.paths is None
    assert measured.changed_targets is None


def test_a_command_that_is_not_pytest_is_not_applicable() -> None:
    """An absence with a different meaning gets a different word (GDP-6)."""
    measured = exercised_modules(("des", "code-fact"), None, ROOT, TEST_PATHS, ())

    assert measured.measure == NOT_APPLICABLE
    assert measured.paths is None
    assert measured.changed_targets is None


def test_reported_paths_outside_the_candidate_are_not_the_candidate() -> None:
    """Another checkout's `src` answers about code nobody verified was here."""
    measured = exercised_modules(
        ("pytest", "tests"),
        report("/home/other/checkout/src/des/cli/code_fact.py"),
        ROOT,
        TEST_PATHS,
        (),
    )

    assert measured.paths == ()


def test_a_fixture_directory_outside_the_test_paths_is_not_product() -> None:
    """One measure of "a test path", shared with `path_under_test_paths`."""
    measured = exercised_modules(
        ("pytest", "tests"),
        report(f"{ROOT}/src/fixtures/stand_in.py", f"{ROOT}/src/real.py"),
        ROOT,
        TEST_PATHS,
        (),
    )

    assert measured.paths == ("src/real.py",)


def test_duplicate_reported_paths_collapse_and_sort() -> None:
    measured = exercised_modules(
        ("pytest", "tests"),
        report(f"{ROOT}/src/b.py", f"{ROOT}/src/a.py", f"{ROOT}/src/b.py"),
        ROOT,
        TEST_PATHS,
        (),
    )

    assert measured.paths == ("src/a.py", "src/b.py")


def test_invokes_pytest_reads_the_runner_guaranteed_spellings() -> None:
    assert invokes_pytest(("pytest", "tests")) is True
    assert invokes_pytest(("/usr/bin/pytest", "tests")) is True
    assert invokes_pytest(("python", "-m", "pytest", "-q")) is True
    assert invokes_pytest(("python3", "-m", "pytest")) is True
    assert invokes_pytest(("uv", "run", "pytest", "tests", "-q")) is True
    assert invokes_pytest(("uv", "pytest", "tests")) is False
    assert invokes_pytest(("des", "code-fact")) is False
    assert invokes_pytest(("python", "-c", "import pytest")) is False
