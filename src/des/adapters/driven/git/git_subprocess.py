"""Single SSOT for the read-only git-subprocess seam (AD-22 collapse).

Before this module the helper

    def _git(repo, *args) -> str:
        completed = subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, text=True, check=True
        )
        return completed.stdout

was triplicated byte-identically across ``run_contract_gate``,
``slice_at_completeness`` and ``reverify_slice_commit``. AD-22 (ARCH_TECH_DEBT)
named that triplication a DRY violation; this module is the one canonical home
the three call-sites now import. ``git`` lives behind this single seam, so the
git-free mandate (AD-21) has exactly one place to grep for git usage in the
contract-gate / slice-completeness path.

Pure read of git -- ``check=True`` so a non-zero git (or a missing executable)
raises, and the call-sites translate that into their LOUD degrade signal
(``Indeterminate`` / refusal). No filesystem mutation.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


def git_text(repo: Path, *args: str) -> str:
    """Run a git command in ``repo`` and return stdout (raises on non-zero).

    Byte-for-byte identical to the three former ``_git`` copies: a checked,
    text-mode ``git`` subprocess rooted at ``repo`` whose stdout is returned.
    """
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout
