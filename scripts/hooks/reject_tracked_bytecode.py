"""Reject staged compiled-bytecode artifacts (.pyc/.pyo/__pycache__).

Regression for defect `deliver-hook-misses-committed-pyc`: 17 tracked .pyc files
landed across 9 commits though .gitignore forbids them -- no pre-commit gate ever
inspected the STAGED file set for gitignore-forbidden bytecode paths, so a
force-add (`git add -f`) or an editor auto-stage slipped them straight past every
existing hook (none of which scans for this pattern).

Pure predicate (`_is_forbidden_bytecode_path`) is unit-testable without git;
`main()` reads `git diff --cached --name-only --diff-filter=ACM` (staged
Added/Copied/Modified paths) and rejects the commit LOUD, naming every offending
path, if any matches. Mirrors `check_merge_conflicts.py`'s shape (a local,
git-free-at-the-predicate-layer, all-tracked-file-scope security hook).
"""

from __future__ import annotations

import subprocess
import sys


_FORBIDDEN_SUFFIXES = (".pyc", ".pyo")
_FORBIDDEN_DIR_SEGMENT = "__pycache__"


def _is_forbidden_bytecode_path(path: str) -> bool:
    """True iff `path` is a compiled-bytecode artifact `.gitignore` forbids."""
    if not path:
        return False
    if path.endswith(_FORBIDDEN_SUFFIXES):
        return True
    return _FORBIDDEN_DIR_SEGMENT in path.split("/")


def _staged_paths() -> list[str]:
    """Every staged Added/Copied/Modified path (`git diff --cached --name-only`)."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True,
        text=True,
        check=False,
        stdin=subprocess.DEVNULL,
        timeout=30,
    )
    return [line for line in result.stdout.splitlines() if line]


def main() -> int:
    offenders = [path for path in _staged_paths() if _is_forbidden_bytecode_path(path)]
    if offenders:
        print(
            "REJECTED: compiled-bytecode artifact(s) staged for commit "
            "(.gitignore forbids .pyc/.pyo/__pycache__):"
        )
        for path in offenders:
            print(f"  {path}")
        print(
            "Fix: `git restore --staged <path>` each offender, delete the file "
            "(or leave it untracked), and re-commit -- bytecode is a build "
            "artifact, never source."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
