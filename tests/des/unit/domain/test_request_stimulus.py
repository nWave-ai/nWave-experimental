"""Path measurements for design-declared native verification argv values."""

from __future__ import annotations

from des.domain.request_stimulus import (
    DEFAULT_TEST_PATHS,
    declared_test_paths,
    path_under_test_paths,
    touches_test_paths,
)


def test_a_declared_verification_reaching_a_fixture_directory_is_measured():
    """Run 24's declared `python -c`, whose path lived inside the program body."""
    argv = (
        "python",
        "-c",
        "sys.path.insert(0,'tests/des/unit/adapters/driven/codefact/fixtures')",
    )

    assert touches_test_paths(argv, ("tests",)) is True


def test_a_fixtures_directory_outside_the_declared_test_paths_still_counts():
    assert touches_test_paths(("pytest", "src/support/fixtures/x.py"), ("tests",))


def test_a_command_naming_only_production_paths_touches_no_test_path():
    argv = ("des", "code-fact", "query.callers-of", "symbol", "--root", ".")

    assert touches_test_paths(argv, ("tests",)) is False


def test_a_prefix_that_is_not_a_path_segment_does_not_match():
    """`tests` and `testsuite` share five characters and no path segment."""
    assert touches_test_paths(("pytest", "testsuite/x.py"), ("tests",)) is False


def test_the_subject_declares_its_own_test_paths():
    text = '[tool.pytest.ini_options]\ntestpaths = ["suite", "other"]\n'

    assert declared_test_paths(text) == ("suite", "other")


def test_a_testpaths_line_in_another_table_is_not_read():
    text = '[tool.other]\ntestpaths = ["wrong"]\n\n[tool.pytest.ini_options]\nx = 1\n'

    assert declared_test_paths(text) == DEFAULT_TEST_PATHS


def test_a_subject_declaring_nothing_falls_back_to_the_conventional_directory():
    assert declared_test_paths(None) == DEFAULT_TEST_PATHS
    assert declared_test_paths("") == DEFAULT_TEST_PATHS


def test_a_subject_declaring_nothing_counts_the_node_test_directory_too():
    """A Node subject has no pyproject.toml and keeps its suite under `test/`.

    Measured 2026-09-15: with `tests` as the only default, an acceptance author's
    `test/*.test.mjs` oracle and its `test/helpers/` fixture module were refused
    as ProductionScopeDrift, so no oracle could ever be authored in that subject.
    """
    defaults = declared_test_paths(None)

    assert "tests" in defaults
    assert "test" in defaults
    assert path_under_test_paths("test/timing-calculator.test.mjs", defaults)
    assert path_under_test_paths("test/helpers/timing-fixtures.mjs", defaults)


def test_the_node_test_directory_matches_a_whole_segment_only():
    defaults = declared_test_paths(None)

    assert not path_under_test_paths("testing/x.mjs", defaults)
    assert not path_under_test_paths("src/test_utils.mjs", defaults)


def test_a_subject_that_declares_test_paths_does_not_inherit_the_default():
    text = '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n'

    assert not path_under_test_paths("test/x.py", declared_test_paths(text))
