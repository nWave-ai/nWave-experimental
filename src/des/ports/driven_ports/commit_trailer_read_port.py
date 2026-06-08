"""CommitTrailerReadPort -- driven port over a repo's commit-message stream.

slice-01 of gate-trailer-read-git-port-extract (DESIGN Reuse Analysis,
AD-24 leg). The deliver-integrity done-gate reconciles shipped slices by reading
the `Slice-Id:`/`Step-Id:` trailers carried in the commit history. This port
supplies that raw message stream: the tuple of commit-message bodies read via
`git log --format=%B%x1e`, exactly the `ChangedSymbolPort` shape this is modeled
on.

git enters ONLY behind this port's adapter
(``des.adapters.driven.git.git_commit_trailer_read_adapter.GitCommitTrailerReadAdapter``);
per ``feedback_target_machine_independence_2026_05_15`` (AD-21) the gate LOGIC
stays git-free and the port's degrade-LOUD ``Indeterminate`` (git absent / not a
work-tree) NEVER fabricates an empty ``CommitMessages(())`` silent pass -- a git
failure surfaces LOUD, never a silent empty message stream the done-gate would
read as "nothing shipped".

``Indeterminate`` is REUSED from ``des.ports.driven_ports.committed_scope_port``
(the same degrade-LOUD VO -- not redefined here), exactly as
``changed_symbol_port.py`` / ``feature_delta_port`` do.

Pure read -- no filesystem mutation (the done-gate is a pure observer of the
trailer history; the port exposes NO write method, principle 12 effect-isolation).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.ports.driven_ports.committed_scope_port import Indeterminate


if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class CommitMessages:
    """The raw commit-message bodies read from a repo's history.

    Frozen observation: the tuple of commit-message bodies (the
    ``%B%x1e``-joined ``git log`` output, pre-split on the record separator). An
    empty ``CommitMessages(())`` is the LEGITIMATE git-SUCCESS "no commits"
    signal; it is NEVER used to mask a git failure -- that degrades to
    ``Indeterminate`` instead. Mirrors ``ChangedSymbols``.
    """

    messages: tuple[str, ...]


class CommitTrailerReadPort(ABC):
    """Driven, read-only port over a repo's commit-message stream.

    The done-gate defines WHAT the trailer history is (the message stream it
    scans for `Slice-Id:` trailers); the adapter decides HOW to read it out of
    git. ``commit_messages`` returns the repo's commit-message bodies, or an
    ``Indeterminate`` when git is absent / ``repo`` is not a work-tree. Pure read
    -- no filesystem mutation (the gate is a pure observer; the port exposes NO
    write method).
    """

    @abstractmethod
    def commit_messages(self, repo: Path) -> CommitMessages | Indeterminate:
        """Return the repo's commit-message stream, or Indeterminate.

        The stream is ``git log --format=%B%x1e`` (each commit body terminated by
        the ASCII record separator). git exiting non-zero -- ``repo`` is not a
        work-tree -- or the git binary being absent yields ``Indeterminate``: the
        gate degrades LOUD rather than fabricate an empty message stream it could
        not read.
        """
        ...


__all__ = ["CommitMessages", "CommitTrailerReadPort", "Indeterminate"]
