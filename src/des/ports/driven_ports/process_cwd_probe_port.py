"""ProcessCwdProbePort -- driven port over "which live processes have their
cwd inside a given directory?" (the worktree-removal liveness guard's
strongest signal).

fix-worktree-removal-liveness-guard (Ale-authorised 2026-07-29). The
orchestrator removed a LIVE lane's worktree three times in one session
because `git status --short` answers "is it dirty?", never "is it LIVE?" --
and git has no notion of "a process is running in here". The strongest LIVE
signal a POSIX host can offer is exactly this: is some process's current
working directory inside the worktree right now? Reading it needs `/proc`
(Linux-only); per `feedback_target_machine_independence_2026_05_15` (AD-21)
the triage predicate (`des.domain.worktree_anti_rot_triage`) stays
OS-free and `/proc` enters ONLY behind this read-only driven port, whose
ABSENCE degrades LOUD (`Indeterminate`, REUSED from `committed_scope_port`
-- the same degrade-LOUD VO every sibling port reuses) -- never a silent
"nothing found" that gets read as "safe to remove".

Mirrors the established `CommitDiffPort` / `CommitTreePathPort` shape
(abstract driven port in `ports/`, a real adapter in `adapters/driven/`):
the domain layer defines WHAT liveness means; the adapter decides HOW to
read it off the host.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.ports.driven_ports.committed_scope_port import Indeterminate


if TYPE_CHECKING:
    from pathlib import Path


__all__ = ["Indeterminate", "ProcessCwdMatch", "ProcessCwdProbePort"]


@dataclass(frozen=True)
class ProcessCwdMatch:
    """One live process whose cwd resolves inside the probed directory."""

    pid: int
    cwd: str


class ProcessCwdProbePort(ABC):
    """Driven, read-only port: which live PIDs have their cwd under `path`?

    `pids_with_cwd_under` returns the (possibly empty) tuple of matches, or
    an `Indeterminate` when the probe mechanism itself could not run to
    completion for EVERY candidate process (the mechanism is absent on this
    host, OR at least one candidate process's cwd link could not be read
    for a reason other than "the process is gone") -- the GDP-8 arity
    corollary: a per-item unknown must reach the aggregate, never be
    silently dropped from an otherwise-empty "found nothing" result.
    """

    @abstractmethod
    def pids_with_cwd_under(
        self, path: Path
    ) -> tuple[ProcessCwdMatch, ...] | Indeterminate:
        """Return every live PID whose cwd resolves under `path`, or Indeterminate.

        An empty tuple is a POSITIVE claim ("checked, none found") and is
        returned ONLY when every candidate process was successfully probed.
        """
        ...
