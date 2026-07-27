"""HeuristicImpactedTestSelectorAdapter -- ImpactedTestSelectorPort implementation.

CREATE_NEW file (des-refactor-fixer-swarm slice-01). Tsunami-first (the
``nw-code-analysis-port`` chain), degrading LOUD to the heuristic fallback
(importers of the changed module / same feature dir) when Tsunami is absent --
never a silently-empty impacted set.

BUGFIX (2026-07-26, [[impacted-test-selector-selects-everything-and-its-
premise-is-false]]): slice-01 originally implemented the heuristic floor as
"the whole target worktree IS the fast+impacted subset", on the premise that a
freshly-cut worktree is small. That premise is false -- a git worktree is a
full checkout of the same tree the repo has, not a subset of it -- and the
premise being false is what let every drained item pay a full-suite pytest
run instead of the "fast+impacted" scope the port's own docstring promises.
This is the real heuristic the docstring always described: same-feature-
directory tests, plus tests that import the changed module, computed from the
ACTUAL ``changed_paths`` the caller now passes (see
``RefactorDrainService._run_tests`` / ``GitWorktreePort.changed_paths_since``)
instead of the empty tuple the caller used to pass unconditionally.

No Tsunami dependency is exercised yet; a Tsunami-first tier is a later-slice
addition once a real multi-module target needs even narrower scoping than the
heuristic floor gives.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from des.ports.driven_ports.impacted_test_selector_port import (
    ImpactedTestSelection,
    ImpactedTestSelectorPort,
)


#: Directory-name components too generic to name a "feature" on their own
#: (structural/layering names that recur across many unrelated features).
#: Walking a changed file's ancestor directories, the first name NOT in this
#: set is treated as its feature name -- e.g. ``src/des/adapters/driven/
#: refactor/foo.py`` yields ``"refactor"``, not ``"adapters"`` or ``"driven"``.
_GENERIC_DIR_NAMES = frozenset(
    {
        "src",
        "des",
        "adapters",
        "driven",
        "drivers",
        "driven_ports",
        "driver_ports",
        "ports",
        "application",
        "domain",
        "cli",
        "scripts",
        "tests",
        "unit",
        "integration",
        "acceptance",
        "e2e",
    }
)

#: Known source roots to strip when deriving a changed file's dotted module
#: path (``src/des/foo/bar.py`` -> ``des.foo.bar``, ``scripts/foo/bar.py`` ->
#: ``foo.bar``). Order matters: longest/most-specific first.
_SOURCE_ROOT_PREFIXES = ("src/", "scripts/")


def _feature_dir_name(changed_path: str) -> str | None:
    """The first non-generic ancestor directory name of ``changed_path``, or
    ``None`` when every ancestor (down to a shallow depth) is a generic
    structural name -- "there is no feature-shaped name to search for", the
    honest absence rather than a misleading guess."""
    parts = Path(changed_path).parent.parts
    for name in reversed(parts):
        if name and name not in _GENERIC_DIR_NAMES:
            return name
    return None


def _dotted_module_path(changed_path: str) -> str | None:
    """The dotted import path a changed ``.py`` file is reached by, or
    ``None`` for a non-Python path (nothing to search import statements for).
    """
    if not changed_path.endswith(".py"):
        return None
    relative = changed_path
    for prefix in _SOURCE_ROOT_PREFIXES:
        if relative.startswith(prefix):
            relative = relative[len(prefix) :]
            break
    without_suffix = relative[: -len(".py")]
    if without_suffix.endswith("/__init__"):
        without_suffix = without_suffix[: -len("/__init__")]
    dotted = without_suffix.replace("/", ".").strip(".")
    return dotted or None


def _importer_test_dirs(tests_root: Path, dotted_module: str) -> set[Path]:
    """Directories of test files that import ``dotted_module`` (or a
    submodule reached through it), matched WORD-BOUNDED -- never a bare
    substring match (the exact false-negative/false-positive class already
    catalogued in this pile as
    [[failure-mode-coverage-decided-by-bare-substring-match-on-test-names]]).
    A short dotted path is still precise here because it is a DOTTED PATH,
    not a bare identifier: ``des.cli`` cannot accidentally match inside an
    unrelated word the way a 2-letter mode id can.
    """
    pattern = re.compile(r"(?<!\w)" + re.escape(dotted_module) + r"(?=\.|\W|$)")
    found: set[Path] = set()
    if not tests_root.is_dir():
        return found
    for test_file in tests_root.rglob("*.py"):
        try:
            text = test_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if pattern.search(text):
            found.add(test_file.parent)
    return found


def _same_feature_test_dirs(tests_root: Path, feature_name: str) -> set[Path]:
    """Every directory under ``tests_root`` whose own name equals
    ``feature_name`` -- this repo groups tests by feature theme (e.g. all of
    ``tests/des/refactor/`` covers the ``refactor`` feature regardless of
    which src layer -- application/domain/adapters -- a changed file sits in),
    not by mirrored full path."""
    if not tests_root.is_dir():
        return set()
    return {d for d in tests_root.rglob(feature_name) if d.is_dir()}


class HeuristicImpactedTestSelectorAdapter(ImpactedTestSelectorPort):
    """Real adapter -- heuristic impacted-test selection.

    Narrows to same-feature-directory tests plus importers of the changed
    module when ``changed_paths`` gives it something to narrow against and
    the heuristic finds at least one real candidate; otherwise it falls back
    to the whole repo and says so honestly via ``narrowed=False`` (GDP-8 --
    never let "could not narrow" wear the same face as "narrowed to
    everything").
    """

    def select(
        self, repo: Path, changed_paths: tuple[str, ...]
    ) -> ImpactedTestSelection:
        if not changed_paths:
            # Nothing changed yet (e.g. the drain's pre-agent baseline run) --
            # there is nothing to narrow AGAINST. Not a heuristic miss, a
            # structural absence of input.
            return ImpactedTestSelection(targets=(str(repo),), narrowed=False)

        tests_root = repo / "tests"
        candidates: set[Path] = set()
        for changed_path in changed_paths:
            feature_name = _feature_dir_name(changed_path)
            if feature_name is not None:
                candidates |= _same_feature_test_dirs(tests_root, feature_name)
            dotted = _dotted_module_path(changed_path)
            if dotted is not None:
                candidates |= _importer_test_dirs(tests_root, dotted)

        if not candidates:
            # The heuristic ran and found no candidate -- still "could not
            # narrow", distinct from "narrowed to the whole repo", but the
            # observable fallback scope is the same repo root either way.
            return ImpactedTestSelection(targets=(str(repo),), narrowed=False)

        common = Path(
            _common_ancestor(sorted(str(candidate) for candidate in candidates))
        )
        if str(common) == str(repo) or common == repo:
            # The candidates collapsed all the way back up to the repo root
            # -- e.g. changed files touching unrelated top-level areas -- so
            # this is not a genuine restriction either.
            return ImpactedTestSelection(targets=(str(repo),), narrowed=False)
        return ImpactedTestSelection(targets=(str(common),), narrowed=True)


def _common_ancestor(paths: list[str]) -> str:
    """``os.path.commonpath`` for a non-empty path list, isolated behind a
    named helper so ``select`` reads as the decision it is, not a stdlib
    incantation."""

    return os.path.commonpath(paths)
