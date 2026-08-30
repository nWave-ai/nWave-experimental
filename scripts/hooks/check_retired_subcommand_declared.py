#!/usr/bin/env python3
"""Pre-commit gate: a `des` subcommand silently dropped from `_REGISTRY`
without a matching `_RETIRED` entry blocks the commit (F-INSTALL-REMOVAL-
TRANSPARENCY, follow-up: "the fix reproduces one level up the same defect it
repairs" -- Ale).

WHY this exists: `des.cli.registry_diff` (this fix's own new module) diffs
`_REGISTRY` names between an old install and a new one so removals are
LOGGED. But nothing stopped the removal itself from being undeclared in the
first place -- tomorrow, someone deletes a `_SubcommandRow` line, never
touches `_RETIRED`, and `des <that-name>` is back to argparse's bare
"invalid choice". This gate makes that specific silent removal
UNREPRESENTABLE in a commit (GDP-0): the property it checks is about the
CHANGE (old `_REGISTRY` vs staged `_REGISTRY`), not about repo state, so it
can be armed today on an already-imperfect history without a backfill.

Scope: fires ONLY when `src/des/cli/__main__.py` is staged -- GDP-1/GDP-5,
no cost on an unrelated commit. Reuses `des.cli.registry_diff` (this same
fix's own reader) rather than a second AST walker (GDP-10).
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


# `src` is put on the path explicitly, not assumed: this hook runs as bare
# `python3 scripts/hooks/check_retired_subcommand_declared.py`, no `uv run`
# and no installed package (same reasoning as pytest_touched_files.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from des.cli.registry_diff import (
    registry_names_from_source,
    retired_names_declared,
)
from des.runtime.spawn import spawn


_TRACKED_PATH = "src/des/cli/__main__.py"


def undeclared_removed_names(
    old_names: frozenset[str],
    new_names: frozenset[str],
    retired_names: frozenset[str],
) -> frozenset[str]:
    """Names present in *old_names*, absent from *new_names*, and absent
    from *retired_names* -- the pure predicate this gate blocks on.
    """
    return frozenset(old_names - new_names - retired_names)


def _staged_files() -> list[str]:
    try:
        result = spawn(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, OSError):
        return []
    return result.stdout.strip().splitlines() if result.stdout.strip() else []


def _old_registry_names(repo_root: Path) -> frozenset[str] | None:
    """`_REGISTRY` names at HEAD, or an empty set when the file is new
    (nothing at HEAD to have silently dropped a name from).
    """
    try:
        result = spawn(
            ["git", "show", f"HEAD:{_TRACKED_PATH}"],
            check=True,
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
    except (subprocess.CalledProcessError, OSError):
        return frozenset()  # no HEAD version -- brand-new file, nothing removable

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(result.stdout)
        temp_path = Path(handle.name)
    try:
        return registry_names_from_source(temp_path)
    finally:
        temp_path.unlink(missing_ok=True)


def main() -> int:
    if _TRACKED_PATH not in _staged_files():
        return 0  # GDP-1/GDP-5: nothing staged that could silently drop a name

    # The repo being CHECKED, not the repo this hook script happens to live
    # in: pre-commit always invokes hooks with cwd = repo root, and the
    # test suite exercises this hook against a throwaway repo the same
    # way. `src` was already put on sys.path above, relative to __file__,
    # purely to import `des.cli.registry_diff` -- that import is
    # independent of which repo's files this run is checking.
    repo_root = Path.cwd()
    working_path = repo_root / _TRACKED_PATH

    old_names = _old_registry_names(repo_root)
    if old_names is None:
        print(
            "WHAT: could not parse the HEAD version of "
            f"{_TRACKED_PATH} to compare subcommand names.\n"
            "WHY: this gate cannot tell whether the staged change silently "
            "dropped a subcommand without a readable baseline.\n"
            "HOW: this indicates a corrupt or non-UTF-8 committed file; "
            "investigate `git show HEAD:" + _TRACKED_PATH + "` directly.",
            file=sys.stderr,
        )
        return 1

    new_names = registry_names_from_source(working_path)
    if new_names is None:
        print(
            f"WHAT: could not parse the staged {_TRACKED_PATH} to extract "
            "its `_REGISTRY` subcommand names.\n"
            "WHY: this gate cannot verify no subcommand was silently "
            "dropped when the file it needs to read does not parse.\n"
            "HOW: fix the syntax error in the file you just staged (the "
            "Python Quality gate will also reject it).",
            file=sys.stderr,
        )
        return 1

    removed = old_names - new_names
    if not removed:
        return 0  # nothing removed -- _RETIRED is irrelevant to this commit

    retired_names = retired_names_declared(working_path)
    if retired_names is None:
        print(
            "WHAT: this commit removes subcommand(s) from `_REGISTRY` "
            f"({', '.join(sorted(removed))}), but the staged "
            f"{_TRACKED_PATH} does not declare a readable `_RETIRED` "
            "mapping to verify they were registered as retired.\n"
            "WHY: a subcommand leaving `_REGISTRY` without a matching "
            "`_RETIRED` entry brings back argparse's bare \"invalid "
            'choice" for it -- exactly the transparency gap '
            "F-INSTALL-REMOVAL-TRANSPARENCY fixed.\n"
            f"HOW: add each removed name to `_RETIRED` in {_TRACKED_PATH} "
            "with a one-line reason, in the same dict-literal or "
            "identity-comprehension shape already used there.",
            file=sys.stderr,
        )
        return 1

    undeclared = undeclared_removed_names(old_names, new_names, retired_names)
    if undeclared:
        names = ", ".join(sorted(undeclared))
        print(
            f"WHAT: subcommand(s) removed from `_REGISTRY` without a "
            f"matching `_RETIRED` entry: {names}.\n"
            "WHY: a silently removed subcommand brings back argparse's "
            'bare "invalid choice" for it instead of the WHAT/WHY/HOW '
            "explanation F-INSTALL-REMOVAL-TRANSPARENCY added -- the same "
            "transparency gap the bug report was filed for, one level up.\n"
            f"HOW: add {'each of these names' if len(undeclared) > 1 else names!r} "
            f"to `_RETIRED` in {_TRACKED_PATH} with a one-line reason "
            "(and a `replacement` only when one is actually verified, "
            "never invented).",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
