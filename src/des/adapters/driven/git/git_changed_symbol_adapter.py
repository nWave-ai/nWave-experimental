"""GitChangedSymbolAdapter -- git implementation of ChangedSymbolPort.

slice-01 of oss-dormant-seam-gate (DESIGN D-2, Reuse R5). The concrete git side
of the changed-symbol boundary, mirroring the established ``FeatureDeltaPort`` <->
``GitFeatureDeltaAdapter`` pattern: the gate logic depends on the PORT, this
adapter implements it with ``git diff --diff-filter=A``.

git enters here ONLY (AD-21 git-free mandate; the rule + CLI logic stay
git-free). The EARNED-TRUST invariant this adapter pins: every git failure (binary
absent, ``repo`` not a work-tree, ``base_ref`` unresolvable -> ``git diff``
non-zero / ``FileNotFoundError`` -- ``git_text`` raises ``check=True``) returns
``Indeterminate(reason)``, NEVER an empty ``ChangedSymbols(())``. An empty
``ChangedSymbols(())`` is ONLY returned on git SUCCESS with a genuinely empty
delta -- masking a git failure as an empty delta would fabricate a silent pass
the degrade-LOUD mandate forbids.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from des.adapters.driven.git.git_subprocess import git_text
from des.ports.driven_ports.changed_symbol_port import (
    ChangedSymbolPort,
    ChangedSymbols,
    Indeterminate,
)


if TYPE_CHECKING:
    from pathlib import Path


class GitChangedSymbolAdapter(ChangedSymbolPort):
    """Reads a feature's net-new ADDED-files delta out of git.

    ``changed_symbols`` returns the repo-relative files ADDED since the merge-base
    with ``base_ref`` (``{base_ref}...HEAD``), or an ``Indeterminate`` when git is
    absent / ``repo`` is not a work-tree / ``base_ref`` is unresolvable. Pure read
    of the git history -- no filesystem mutation.
    """

    def changed_symbols(
        self, repo: Path, base_ref: str
    ) -> ChangedSymbols | Indeterminate:
        """Return the feature's ADDED-files delta, or Indeterminate.

        ``git diff --diff-filter=A --name-only {base_ref}...HEAD`` (three-dot:
        added since the merge-base with ``base_ref``). A missing git binary
        (``FileNotFoundError``) or a non-zero exit (``repo`` not a work-tree,
        ``base_ref`` unresolvable -> ``CalledProcessError`` from ``git_text``'s
        ``check=True``) degrades LOUD to ``Indeterminate`` -- never an empty
        ``ChangedSymbols(())`` that would silently read downstream as "nothing
        dormant".
        """
        try:
            stdout = git_text(
                repo,
                "diff",
                "--diff-filter=A",
                "--name-only",
                f"{base_ref}...HEAD",
            )
        except FileNotFoundError as exc:
            return Indeterminate(f"git binary not found: {exc}")
        except subprocess.CalledProcessError as exc:
            return Indeterminate(
                f"git diff failed (exit {exc.returncode}): "
                f"{(exc.stderr or '').strip()[:200]}"
            )
        paths = tuple(line for line in stdout.splitlines() if line)
        return ChangedSymbols(paths)


__all__ = ["GitChangedSymbolAdapter"]
