"""The Request author's own executable stimulus, read out of the Request text.

MEASURED (run 24, 2026-09-05; `defects.md`, row
`des-integrated-a-fixture-only-fix-the-real-query-still-answers-empty`).  The
Request named its stimulus in backticks -- `des code-fact query.callers-of
resolve_declared_capability --root .` -- and the architect declared, as its
native verification, a `python -c` that inserted a TEST FIXTURE directory on
`sys.path` and drove the stand-in module found there.  Every role downstream saw
an exit-0 execution of a command nobody could tell apart from the real one, and
a candidate touching no production byte was integrated.

Two facts were missing, and both are MEASUREMENTS rather than judgements
(`boundary:software-measures-model-decides`):

* what the stimulus WRITTEN BY THE HUMAN answers when it runs against the
  candidate -- an oracle no role in the run may rewrite, because no role wrote
  it; and
* whether a declared verification argv reaches into the subject's own test
  paths.

This module owns the first half of each: which spans of a Request are executable
stimuli, and whether an argv touches test paths.  It decides nothing about what
either fact means -- that is the reviewer's and the examiner's to judge.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import PurePosixPath


#: An inline code span: one backtick, no newline inside, and no adjacent
#: backtick on either side so a fenced block or a ``code`` span is never
#: mistaken for one.  The measure of "a command and not prose" is deliberately
#: this plus the head table below -- an inline code span whose first word is a
#: tool the runtime provides.  No semantic parse, nothing to be wrong about.
_INLINE_CODE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")

#: Heads the native verification runtime GUARANTEES resolve to the CANDIDATE's
#: own code: `_candidate_runtime` arms a shim for each one before any command
#: runs.  A stimulus starting with any other word is not extracted at all, which
#: is also why no destructive spelling can be: `rm`, `git push` and a redirection
#: all fail the head test, and nothing is ever handed to a shell.
EXECUTED_HEADS = ("des", "python", "python3", "pytest")

#: Extracted and recorded, never run.  `uv` is not a runtime dependency of DES
#: and no shim is armed for it, so `uv run` would resolve to whatever the box
#: happens to carry -- the wrong-projection class run 17 measured -- and it
#: writes into a cache outside the candidate.  Recording it as not executed,
#: with this reason, degrades LOUD (GDP-6) where executing it would answer
#: confidently about code nobody verified was the candidate's.
_WITHHELD = (("uv", "run"),)
_WITHHELD_REASON = (
    "the candidate runtime arms shims only for "
    f"{', '.join(EXECUTED_HEADS)}, so this command would resolve outside the "
    "candidate and write outside it"
)


@dataclass(frozen=True, slots=True)
class RequestStimulus:
    """One command the Request's author wrote, and whether it may be run.

    `withheld` is empty when the runner executes the argv, and carries the
    reason when it does not.  A withheld stimulus is still reported: the fact
    that the human named a stimulus the runner cannot run is itself evidence.
    """

    argv: tuple[str, ...]
    withheld: str = ""


def request_stimuli(text: str) -> tuple[RequestStimulus, ...]:
    """Every executable command the Request text names, in the author's order.

    Identical spellings collapse to one, keeping the first occurrence: the same
    command run twice measures the same thing twice and doubles the prompt.
    """
    found: dict[tuple[str, ...], RequestStimulus] = {}
    for span in _INLINE_CODE.findall(text):
        argv = _argv(span)
        if argv is None or argv in found:
            continue
        found[argv] = RequestStimulus(argv, _withheld(argv))
    return tuple(found.values())


def _argv(span: str) -> tuple[str, ...] | None:
    """A code span as an argv, or None when it is not an admitted command."""
    try:
        parts = shlex.split(span)
    except ValueError:
        return None
    if len(parts) < 2:
        # A single bare word in backticks is a NAME, not an invocation: run 23's
        # Request spells `des`, `links`, `edges` and `name()` that way, and only
        # the first would pass the head table.  Two tokens is the cheapest
        # SYNTACTIC line between naming a tool and invoking it, and it is stated
        # here as a limit rather than hidden: a Request whose whole stimulus is
        # a bare `pytest` is not extracted, and no measure short of reading the
        # sentence around it could tell that case from the noun.
        return None
    head = PurePosixPath(parts[0]).name
    if head not in EXECUTED_HEADS and not any(
        parts[: len(prefix)] == list(prefix) for prefix in _WITHHELD
    ):
        return None
    return tuple(parts)


def _withheld(argv: tuple[str, ...]) -> str:
    for prefix in _WITHHELD:
        if argv[: len(prefix)] == prefix:
            return _WITHHELD_REASON
    return ""


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
#: the flag stays a claim about paths rather than about collection.
DEFAULT_TEST_PATHS = ("tests",)

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
