"""Which of the subject's PRODUCT files a native verification run imported.

MEASURED (run 34, 2026-09-06 03:45; same class run 27, `defects.md` row
`touches-test-paths-is-true-for-every-pytest-argv-and-rejected-a-product-driving-oracle`).
The examiner refused candidate 6a8e46cde because two of its three causes "are
only exercised inside pytest runs of test modules whose touches_test_paths is
true", and the orchestrator then verified those causes by hand against the real
root and integrated.  The rejected oracle drives `des.cli.code_fact.main`
in-process on a temporary root: it exercises the product.

`touches_test_paths` is a true and useful measurement, and it is BINARY over the
argv's paths -- so it is true for every pytest argv ever written.  It caught run
24, whose declared verification drove a stand-in module under the subject's own
test tree, and it rejected run 34, whose oracle drove the product from the same
kind of path.  One bit cannot separate those two, because the difference is not
in the argv at all: it is in what the session IMPORTED.

This module owns that second fact and decides nothing with it.  GDP-8: the
PROPERTY (which product files the run loaded), never the DESIGNATION (where the
argv's path arguments sit).  Whether a promise is observed on the product stays
the examiner's and the whole-diff reviewer's judgement
(`boundary:software-measures-model-decides`).
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from pathlib import PurePosixPath

from des.domain.request_stimulus import path_under_test_paths


#: The session reached `pytest_sessionfinish` and reported what it had loaded.
MEASURED = "measured"

#: The argv names pytest and no report arrived: the session never finished, so
#: the empty list would be a LIE about the run rather than a fact about it
#: (GDP-6, degrade LOUD).
INDETERMINATE = "indeterminate"

#: No report, and the argv names no pytest to have written one.  A different
#: absence deserves a different word: `des code-fact ...` imports the product
#: too, but not through a session this measure can observe.
NOT_APPLICABLE = "not-applicable"

#: Recognized pytest invocations that arm the existing session probe.
#: Recognizing `uv run pytest` does not provide or install the `uv` executable.
#:
#: STATED LIMIT.  A `python -c` body that calls `pytest.main()` is not read as
#: pytest here, and no measure short of parsing the program could tell it from
#: prose.  Such a command is reported NOT_APPLICABLE rather than measured: the
#: runner arms the session probe only where this answers true, so that it can
#: leave every other command's environment byte for byte as it inherited it.
#: The consequence is an ABSENT fact, never a wrong one -- and the argv, the
#: exit status and `touches_test_paths` still sit beside it.
_PYTEST = "pytest"


@dataclass(frozen=True, slots=True)
class ExercisedModules:
    """One native execution's answer about the product code it loaded.

    `paths` and `changed_targets` are None together, and only when `measure` is
    not `MEASURED`: an unmeasured run has no list, and an empty list is reserved
    for the run that finished having loaded nothing -- run 24's shape, which is
    exactly the fact worth seeing.
    """

    measure: str
    paths: tuple[str, ...] | None
    changed_targets: tuple[str, ...] | None


def invokes_pytest(argv: tuple[str, ...]) -> bool:
    """Whether this argv names pytest as the program it starts.

    Read ONLY to name an absence: the presence of a session report is what says
    a run was measured, so a wrong answer here never turns a measured run into
    an unmeasured one.
    """
    if not argv:
        return False
    if PurePosixPath(argv[0]).name == _PYTEST:
        return True
    if (
        PurePosixPath(argv[0]).name == "uv"
        and len(argv) >= 3
        and argv[1:3] == ("run", _PYTEST)
    ):
        return True
    return any(first == "-m" and second == _PYTEST for first, second in pairwise(argv))


def exercised_modules(
    argv: tuple[str, ...],
    report: str | None,
    root: str,
    test_paths: tuple[str, ...],
    changed: tuple[str, ...],
) -> ExercisedModules:
    """The product files `argv` loaded, and which of the candidate's it changed.

    `report` is the text the session plugin wrote, or None when no session
    wrote one.  `root` is the candidate tree the paths must sit inside, already
    resolved by the caller -- a reported file under another checkout answers
    about code nobody verified was this candidate's, which is the same
    silent-wrong `_candidate_runtime` closes for the interpreter.

    `changed` are the candidate's changed paths, repository-relative, exactly as
    Git reports them.  The intersection is delivered as numbers and lists; no
    threshold and no verdict live here.
    """
    if report is None:
        return ExercisedModules(
            INDETERMINATE if invokes_pytest(argv) else NOT_APPLICABLE, None, None
        )
    paths = _product_paths(report, root, test_paths)
    targets = tuple(path for path in paths if path in _product(changed, test_paths))
    return ExercisedModules(MEASURED, paths, targets)


def _product_paths(
    report: str, root: str, test_paths: tuple[str, ...]
) -> tuple[str, ...]:
    prefix = PurePosixPath(root)
    relative = []
    for line in report.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        path = PurePosixPath(candidate)
        try:
            inside = path.relative_to(prefix)
        except ValueError:
            continue
        relative.append(inside.as_posix())
    return _product(tuple(relative), test_paths)


def _product(paths: tuple[str, ...], test_paths: tuple[str, ...]) -> tuple[str, ...]:
    """Everything that is not test scaffolding, sorted and collapsed.

    "Product" is defined as the complement of `path_under_test_paths`, reusing
    the one measure `touches_test_paths` already uses, so the two facts placed
    side by side in the evidence cannot drift apart on what a test path is.
    """
    return tuple(
        sorted({path for path in paths if not path_under_test_paths(path, test_paths)})
    )
