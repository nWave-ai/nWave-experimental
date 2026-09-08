"""The two measurements behind the Request-stimulus evidence, in isolation.

Neither function decides anything.  One says which spans of a Request text are
commands the candidate runtime can run; the other says whether an argv reaches
into the subject's declared test paths.  The judgements those facts feed live in
the examiner's and the reviewer's turns, and nothing here anticipates them.
"""

from __future__ import annotations

from des.domain.request_stimulus import (
    DEFAULT_TEST_PATHS,
    declared_test_paths,
    request_stimuli,
    touches_test_paths,
)


REQUEST_23 = (
    "Make `des code-fact query.callers-of` report the real call sites.\n\n"
    "`des code-fact query.callers-of resolve_declared_capability --root .` exits "
    "0 and answers `sites: []`, although the adapter iterates the key `edges` "
    "while graphify emits node-link JSON under the key `links`, comparing the "
    "bare symbol against labels carrying a trailing `name()`.\n"
)


def argvs(text):
    return [item.argv for item in request_stimuli(text)]


def test_the_authors_own_command_is_read_out_of_the_request_text():
    """Run 23's Request names two spans starting with a tool, and both are read.

    The first is the subcommand alone, in the title sentence; the second is the
    whole invocation, with its symbol and root.  Extraction does NOT try to tell
    a complete command from a partial one -- that would be the semantic parse
    this measure exists to avoid, and it would be the runner deciding which of
    the author's words counted.  The partial one runs, answers a usage error,
    and the reader sees exactly that.
    """
    assert argvs(REQUEST_23) == [
        ("des", "code-fact", "query.callers-of"),
        (
            "des",
            "code-fact",
            "query.callers-of",
            "resolve_declared_capability",
            "--root",
            ".",
        ),
    ]


def test_prose_in_backticks_is_not_a_command():
    """The head table is the whole measure of "code and not prose".

    `links`, `name()` and `sites: []` are all inline code spans in run 23's
    Request, and none of them starts with a tool the candidate runtime arms.
    """
    assert argvs("the key `links`, the label `name()`, the answer `sites: []`") == []


def test_a_bare_tool_name_is_a_noun_and_not_an_invocation():
    """Run 23's Request writes `des` alone while naming the installed executable."""
    assert argvs("it does not spawn the installed `des` executable") == []


def test_a_fenced_block_is_not_an_inline_span():
    assert argvs("```\npytest -q\n```\n") == []


def test_the_same_command_written_twice_is_measured_once():
    assert argvs("`pytest -q` then again `pytest -q`") == [("pytest", "-q")]


def test_a_command_the_runtime_arms_no_shim_for_is_recorded_and_withheld():
    """`uv` resolves outside the candidate and writes outside it, so it is
    reported as a stimulus the author named and the runner did not run."""
    (stimulus,) = request_stimuli("reproduce with `uv run pytest -q`")

    assert stimulus.argv == ("uv", "run", "pytest", "-q")
    assert "arms shims only for" in stimulus.withheld


def test_an_unbalanced_quote_yields_no_command():
    assert argvs('`python -c "open(`') == []


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
