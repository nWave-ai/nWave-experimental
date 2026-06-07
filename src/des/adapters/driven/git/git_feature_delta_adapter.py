"""GitFeatureDeltaAdapter -- git implementation of FeatureDeltaPort.

slice-03 of fix-feature-end-ws-gate-applicability (Ale-ratified option B-port,
2026-06-05). The concrete git side of the feature-delta boundary, mirroring the
established ``CommittedScopePort`` <-> ``GitCommittedScopeAdapter`` pattern: the
gate logic depends on the PORT, this adapter implements it with ``git diff
--diff-filter=A``.

git enters here ONLY (AD-21 git-free mandate). The EARNED-TRUST invariant this
adapter pins: every git failure (binary absent, ``repo`` not a work-tree,
``base_ref`` unresolvable -> ``git diff`` non-zero / ``FileNotFoundError``)
returns ``Indeterminate(reason)``, NEVER an empty ``AddedPaths(())``. An empty
``AddedPaths(())`` is ONLY returned on git SUCCESS with a genuinely empty delta --
masking a git failure as an empty delta would fabricate a silent NA pass the
degrade-LOUD mandate forbids.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from des.ports.driven_ports.feature_delta_port import (
    AddedPaths,
    FeatureDeltaPort,
    Indeterminate,
)


if TYPE_CHECKING:
    from pathlib import Path


class GitFeatureDeltaAdapter(FeatureDeltaPort):
    """Reads a feature's ADDED-paths delta out of git (``git diff --diff-filter=A``).

    ``added_paths`` returns the repo-relative files ADDED since the merge-base
    with ``base_ref`` (``{base_ref}...HEAD``), or an ``Indeterminate`` when git is
    absent / ``repo`` is not a work-tree / ``base_ref`` is unresolvable. Pure read
    of the git history -- no filesystem mutation.
    """

    def added_paths(self, repo: Path, base_ref: str) -> AddedPaths | Indeterminate:
        """Return the feature's ADDED-paths delta, or Indeterminate.

        ``git diff --diff-filter=A --name-only {base_ref}...HEAD`` (three-dot:
        added since the merge-base with ``base_ref``). A missing git binary
        (``FileNotFoundError``) or a non-zero exit (``repo`` not a work-tree,
        ``base_ref`` unresolvable) degrades LOUD to ``Indeterminate`` -- never an
        empty ``AddedPaths(())`` that would silently read downstream as NA.
        """
        try:
            result = subprocess.run(
                [
                    "git",
                    "diff",
                    "--diff-filter=A",
                    "--name-only",
                    f"{base_ref}...HEAD",
                ],
                cwd=repo,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            return Indeterminate(f"git binary not found: {exc}")
        if result.returncode != 0:
            return Indeterminate(
                f"git diff failed (exit {result.returncode}): "
                f"{result.stderr.strip()[:200]}"
            )
        paths = tuple(line for line in result.stdout.splitlines() if line)
        return AddedPaths(paths)


__all__ = ["GitFeatureDeltaAdapter"]
