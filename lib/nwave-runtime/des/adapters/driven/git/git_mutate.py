"""Single SSOT for the git-MUTATION subprocess seam (commit-slice flow).

The read-only counterpart is ``git_subprocess.git_text`` (AD-22). This module
is its mutation sibling: the one canonical place where ``des commit-slice``
stages, commits and amends. git enters here ONLY (AD-21 git-free mandate): the
``commit-slice`` CLI depends on this thin seam, so a git-absent target degrades
LOUD at exactly one greppable boundary rather than a baked-in requirement
sprinkled across the orchestration.

``check=True`` so a non-zero git (or a missing executable) raises, and the
caller translates that into its LOUD degrade signal. Unlike ``git_text`` this
seam DOES mutate the work-tree / refs -- it is invoked only by the
operator-driven ``commit-slice`` console subcommand, never by a read-only gate.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


def git_run(repo: Path, *args: str) -> str:
    """Run a MUTATING git command in ``repo`` and return stdout (raises on non-zero).

    A checked, text-mode ``git`` subprocess rooted at ``repo``. ``stderr`` is
    captured and folded into the raised ``CalledProcessError`` so the caller can
    surface a diagnosable LOUD failure rather than a bare traceback.
    """
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout
