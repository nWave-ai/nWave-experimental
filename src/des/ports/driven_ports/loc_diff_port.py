"""LocDiffPort — the driven port for the git-diff test-LOC cross-check (slice-04).

The unbounded-preservation boundary (DDD-10) the sustainability metrics gate composes:
a READ-ONLY observation of the net test-LOC delta in a working tree against HEAD. git
enters ONLY behind this port (AD-21 git-free mandate; the gate core stays Python +
filesystem). git is NOT a hard dependency — a missing git binary / a non-repo tree
degrades LOUD to ``GitDiffUnavailable`` (never a fabricated zero-delta that would read
downstream as a silent ``consistent`` pass, DDD-4).

The port returns the typed pure-core value verbatim (``TestLocDelta`` |
``GitDiffUnavailable``) — the classification (`classify_blind_add`) is pure and total
over both.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:
    from pathlib import Path

    from des.domain.sustainability_metrics import GitDiffUnavailable, TestLocDelta


class LocDiffPort(Protocol):
    """Read the net test-LOC delta of a working tree against HEAD — read-only.

    One method: :meth:`test_loc_delta`. NO write method (Principle 12 — an observation
    port only reads). Returns a ``TestLocDelta`` on a successful git read, or a
    ``GitDiffUnavailable`` (carrying the LOUD reason) when the diff cannot be computed.
    """

    def test_loc_delta(self, repo: Path) -> TestLocDelta | GitDiffUnavailable:
        """Return the net test-LOC delta in ``repo`` (working tree vs HEAD)."""
        ...


__all__ = ["LocDiffPort"]
