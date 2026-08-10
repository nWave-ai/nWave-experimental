#!/usr/bin/env python3
"""Classify a changed-paths list as docs-only, fail-closed.

Single source of truth for the "does this push/PR touch ONLY docs/**" question
that gates the CI docs-only fast path (skips test / worktree-topology /
coverage-combine / agent-sync when true). The workflow YAML must never
re-implement this rule; it only computes the diff and pipes it through here.

CLI contract:
    git diff --name-only <base> <head> | python scripts/ci/docs_only_classifier.py
    Reads changed paths on stdin (one per line), prints exactly one line,
    `docs_only=true` or `docs_only=false`, suitable for `>> "$GITHUB_OUTPUT"`.
    Always exits 0 -- this is a classification, not a pass/fail gate; every
    uncertain or malformed case classifies as `false` (fail-closed, full
    test suite runs).

Architecture (functional split):
- Pure core: `is_docs_only_change(paths)` takes a list of strings, returns
  bool. No I/O, no git.
- CLI shell: `main(argv)` reads stdin, delegates to the pure core, prints
  the GITHUB_OUTPUT-formatted line.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Sequence


DOCS_PREFIX = "docs/"


def is_docs_only_change(paths: Sequence[str]) -> bool:
    """Return True iff every path is non-empty and lives strictly under docs/.

    Fail-closed: an empty `paths` sequence (no changed files -- ambiguous,
    treat as "not proven docs-only") and any path that is blank, outside
    docs/, or equal to "docs/" itself (no filename) all classify False.
    """
    if not paths:
        return False
    return all(
        path.startswith(DOCS_PREFIX) and len(path) > len(DOCS_PREFIX) for path in paths
    )


def _format_output(docs_only: bool) -> str:
    return f"docs_only={'true' if docs_only else 'false'}"


def main(argv: list[str] | None = None) -> int:
    """CLI entry: reads changed paths from stdin, prints the GITHUB_OUTPUT line.

    Args:
        argv: unused, accepted for CLI-entry-point symmetry with sibling
            scripts. This classifier takes no flags.

    Returns:
        0 always -- classification failure is expressed as `docs_only=false`
        on stdout, never as a non-zero exit.
    """
    del argv
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    paths = raw.splitlines()
    print(_format_output(is_docs_only_change(paths)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
