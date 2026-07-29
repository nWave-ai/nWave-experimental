"""collect_worktree_triage_receipt -- shared signal-collection + triage call.

EXTRACT (sentinel-sweep-enumerator, 2026-07-29). `scripts/hooks/
worktree_removal_guard.py` originally carried this logic as a private
`_run_triage` function -- until this extraction, the ONLY caller of
`des.domain.worktree_anti_rot_triage.triage_worktree` anywhere in the tree
(see the SENTINEL node in `docs/mikado/EXECUTION-SSOT-des-optimization.md`:
the triage predicate exists but has a single, removal-time-only caller, so
nobody sweeps the linked-worktree set proactively).

Moved here so a SECOND caller -- the periodic Sentinel sweep enumerator,
`des.application.worktree_sentinel_sweep` -- reuses the EXACT SAME
signal-collection instead of re-deriving it. GDP-4 (the "how" invokes the
producing tool, never a hand-rolled duplicate) and the corollary this very
incident names: a predicate without an enumerator forces every caller to
invent its own population/signal-plumbing, and an invented copy usually
drifts. `worktree_removal_guard.py` now imports this function instead of
defining its own copy -- pure extraction, no behavior change.

LATENT TYPE MISMATCH FOUND ON MOVE, FIXED HERE (not carried forward): the
original `_run_triage` passed `ProcessCwdProbePort.pids_with_cwd_under`'s
result -- `tuple[ProcessCwdMatch, ...] | Indeterminate` (the PORT's own VO)
-- straight into `triage_worktree`, which declares `tuple[ProcessMatch,
...] | Indeterminate` (the DOMAIN's own, separately-declared VO). The two
dataclasses are structurally identical (`pid`, `cwd`), so this worked at
runtime and was never caught -- `scripts/hooks/` sits outside `mypy src/
des/`'s strict-checked path. Moving the function into `src/des/application/`
makes it visible. Translated explicitly below rather than silenced: the
hexagonal boundary is real (the port must not leak a domain type, and the
domain must not import port types), so an explicit adapter-boundary mapping
is the correct fix, not a cast.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from des.adapters.driven.git.git_worktree_removal_safety_adapter import (
    GitWorktreeRemovalSafetyAdapter,
)
from des.adapters.driven.process.proc_process_cwd_adapter import ProcProcessCwdAdapter
from des.domain.worktree_anti_rot_triage import (
    ProcessMatch,
    WorktreeAntiRotReceipt,
    triage_worktree,
)
from des.ports.driven_ports.committed_scope_port import Indeterminate
from des.runtime.spawn import SpawnTimeout, spawn


if TYPE_CHECKING:
    from pathlib import Path


def resolve_target_branch(repo: Path) -> str | None:
    """Resolve the CURRENT branch of `repo` (`git rev-parse --abbrev-ref HEAD`).

    This is the DEFAULT resolution every caller falls back to -- the
    orchestrator's own vantage point ("is this worktree's work reachable
    from where I stand"). Returns `None` when git is absent, `repo` is not a
    work tree, or the read times out -- callers pass `None` straight through
    to `collect_worktree_triage_receipt`, which reports that as an
    Indeterminate unmerged-commits signal, never a silent "assume merged"
    (GDP-6). A caller wanting a different reference branch (e.g. an
    operator env-var override) resolves it BEFORE calling this function and
    skips it entirely -- this helper only ever answers "what is `repo`
    currently on".
    """
    try:
        result = spawn(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, SpawnTimeout):
        return None
    if result.returncode != 0:
        return None
    branch = result.stdout.strip()
    return branch or None


def collect_worktree_triage_receipt(
    repo: Path, target_path: Path, target_branch: str | None
) -> WorktreeAntiRotReceipt:
    """Collect the triage predicate's four evidence signals for `target_path`
    and return its receipt.

    `target_branch` is the ALREADY-RESOLVED branch the unmerged-commits axis
    compares against -- `None` means the caller could not resolve one (or
    chose not to), reported here as an Indeterminate unmerged-commits signal
    rather than a silent "assume merged". `repo` is the git repository the
    liveness/dirty/unmerged probes are RUN FROM (the shared `.git`); it need
    not equal `target_path` -- probing a linked worktree's state is always
    done relative to the repo the probe was invoked against.
    """
    process_probe = ProcProcessCwdAdapter()
    port_matches = process_probe.pids_with_cwd_under(target_path)
    process_matches: tuple[ProcessMatch, ...] | Indeterminate = (
        port_matches
        if isinstance(port_matches, Indeterminate)
        else tuple(ProcessMatch(pid=m.pid, cwd=m.cwd) for m in port_matches)
    )

    safety_probe = GitWorktreeRemovalSafetyAdapter()
    locked = safety_probe.is_locked(repo, target_path)
    dirty = safety_probe.has_dirty_state(repo, target_path)

    if target_branch is None:
        unmerged: tuple[str, ...] | Indeterminate = Indeterminate(
            "target branch could not be resolved -- unmerged-commit status unknown"
        )
    else:
        unmerged = safety_probe.has_unmerged_commits(repo, target_path, target_branch)

    return triage_worktree(
        target_path=str(target_path),
        process_matches=process_matches,
        locked=locked,
        dirty=dirty,
        unmerged_commits=unmerged,
    )


__all__ = ["collect_worktree_triage_receipt", "resolve_target_branch"]
