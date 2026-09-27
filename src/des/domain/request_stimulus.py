"""Path measurements for design-declared native verification argv values."""

from __future__ import annotations

import re
from pathlib import PurePosixPath


#: A path-shaped run of characters.  Applied to EVERY argv token rather than to
#: whole tokens, so a path buried inside a `-c` program body -- exactly how run
#: 24's declared verification reached its fixture -- is measured the same way a
#: bare `pytest tests/...` argument is.
_PATHLIKE = re.compile(r"[A-Za-z0-9_.\-/]+")

#: A directory name that is test scaffolding wherever it sits in the tree.  The
#: run-24 fixture lived under the subject's own test paths anyway; this covers
#: the same shape in a repository whose fixtures sit elsewhere.
_FIXTURES = "fixtures"

#: Read when the subject declares no `testpaths`, which is what pytest itself
#: does not do -- it collects from the rootdir.  A repository that declares
#: nothing is therefore measured against its conventional test directory, and
#: the flag stays a claim about paths rather than about collection.  The
#: convention is `tests` for pytest and `test` for Jest and Mocha: measured
#: 2026-09-15, a Node subject with no pyproject.toml had its `test/` oracle
#: refused as production scope drift, so no oracle could be authored there.
DEFAULT_TEST_PATHS = ("tests", "test")

_INI_OPTIONS = re.compile(r"^\s*\[tool\.pytest\.ini_options\]\s*$")
_TABLE = re.compile(r"^\s*\[")
_TESTPATHS = re.compile(r"^\s*testpaths\s*=\s*\[(?P<body>[^\]]*)\]", re.MULTILINE)
_QUOTED = re.compile(r"""["']([^"']+)["']""")


def declared_test_paths(pyproject_text: str | None) -> tuple[str, ...]:
    """The subject's own `[tool.pytest.ini_options] testpaths`, or the default.

    Textual and not a TOML parse, for the reason `repository_format_contract`
    states: the bundled `des/` package carries no TOML dependency and cannot
    grow one, `tomllib` does not exist on the declared 3.10 floor, and a
    malformed file must degrade to the default rather than raise.
    """
    if not pyproject_text:
        return DEFAULT_TEST_PATHS
    lines = pyproject_text.splitlines()
    for index, line in enumerate(lines):
        if not _INI_OPTIONS.match(line):
            continue
        end = index + 1
        while end < len(lines) and not _TABLE.match(lines[end]):
            end += 1
        section = "\n".join(lines[index + 1 : end])
        match = _TESTPATHS.search(section)
        if match:
            declared = tuple(_QUOTED.findall(match.group("body")))
            return declared or DEFAULT_TEST_PATHS
    return DEFAULT_TEST_PATHS


def path_under_test_paths(path: str, test_paths: tuple[str, ...]) -> bool:
    """Whether ONE path sits under a declared test path or a fixtures directory.

    The single measurement both callers ask for, so the argv scan and the
    runner's scope observation cannot drift apart on what "a test path" means.
    A repository whose fixtures sit outside its test paths is covered by the
    `fixtures` segment for the reason `_FIXTURES` states.
    """
    segments = _segments(path)
    if not segments:
        return False
    if _FIXTURES in segments:
        return True
    return any(
        prefix and segments[: len(prefix)] == prefix
        for prefix in (_segments(declared) for declared in test_paths)
    )


def touches_test_paths(argv: tuple[str, ...], test_paths: tuple[str, ...]) -> bool:
    """Whether any path in `argv` sits under a declared test path or a fixtures dir.

    A pure measurement over the argv the runner is about to execute.  Whether a
    promise verified only by such commands counts as observed on the product is
    the model's decision, and this returns nothing that anticipates it.
    """
    return any(
        path_under_test_paths(candidate, test_paths)
        for token in argv
        for candidate in _PATHLIKE.findall(token)
    )


def _segments(path: str) -> list[str]:
    return [part for part in PurePosixPath(path).parts if part not in (".", "/")]
