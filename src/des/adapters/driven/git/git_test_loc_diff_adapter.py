"""GitTestLocDiffAdapter — git implementation of TestLocDiffPort (slice-04, DDD-4/10).

The concrete git side of the test-LOC cross-check boundary, mirroring the established
``ChangedSymbolPort`` <-> ``GitChangedSymbolAdapter`` pattern: the gate logic depends on
the PORT, this adapter implements it with ``git diff --numstat HEAD`` over the working
tree. git enters ONLY here (AD-21 git-free mandate; the rule + gate-core logic stay
git-free).

EARNED-TRUST invariant (DDD-4 / DDD-10): every git failure — binary absent, the tree is
not a work-tree, no ``HEAD`` yet — returns ``GitDiffUnavailable(reason)``, NEVER a
fabricated ``TestLocDelta(0)`` that would read downstream as a silent ``consistent``
pass. A ``TestLocDelta`` is returned ONLY on git success.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from des.adapters.driven.git.git_constants import GIT_HEAD
from des.adapters.driven.git.git_subprocess import git_text
from des.domain.sustainability_metrics import GitDiffUnavailable, TestLocDelta
from des.ports.driven_ports.test_loc_diff_port import TestLocDiffPort


if TYPE_CHECKING:
    from pathlib import Path


def _is_test_path(path: str) -> bool:
    """True when ``path`` is a test-LOC file (a ``tests/`` segment or a test_*/*_test).

    The net test-LOC delta counts ONLY test files (DDD-4 measures the TEST denominator),
    so production-LOC churn never moves the consolidation-delta cell.
    """
    parts = path.split("/")
    if "tests" in parts or "test" in parts:
        return True
    name = parts[-1]
    return name.startswith("test_") or name.endswith(("_test.py", "_test.ts"))


class GitTestLocDiffAdapter(TestLocDiffPort):
    """Reads a working tree's net test-LOC delta against HEAD out of git.

    ``git diff --numstat HEAD`` yields ``<added>\t<deleted>\t<path>`` rows; the net
    test-LOC delta is ``sum(added) - sum(deleted)`` over the test-path rows. A missing
    git binary / non-repo tree / absent HEAD degrades LOUD to ``GitDiffUnavailable``.
    """

    def test_loc_delta(self, repo: Path) -> TestLocDelta | GitDiffUnavailable:
        """Return the net test-LOC delta in ``repo`` (working tree vs HEAD), or LOUD."""
        try:
            stdout = git_text(repo, "diff", "--numstat", GIT_HEAD)
        except FileNotFoundError as exc:
            return GitDiffUnavailable(reason=f"git binary not found: {exc}")
        except subprocess.CalledProcessError as exc:
            return GitDiffUnavailable(
                reason=(
                    f"git diff failed (exit {exc.returncode}): "
                    f"{(exc.stderr or '').strip()[:200]}"
                )
            )
        net = 0
        for line in stdout.splitlines():
            fields = line.split("\t")
            if len(fields) != 3:
                continue
            added_raw, deleted_raw, path = fields
            if not _is_test_path(path):
                continue
            # Binary files report `-` for both counts; they carry no LOC delta.
            if added_raw == "-" or deleted_raw == "-":
                continue
            net += int(added_raw) - int(deleted_raw)
        return TestLocDelta(net=net)


__all__ = ["GitTestLocDiffAdapter"]
