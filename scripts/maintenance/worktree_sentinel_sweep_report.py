#!/usr/bin/env python3
"""Run the Sentinel's worktree anti-rot sweep and print a per-worktree +
summary report.

sentinel-sweep-enumerator (team-lead dispatch 2026-07-29). Thin CLI wrapper
over `des.application.worktree_sentinel_sweep.sweep_worktrees` -- the
enumerator itself carries no printing/formatting; this script is the
operator-facing surface a Sentinel pass (or a human) runs to get the
inventory `nWave/skills/nw-throughput/SKILL.md` describes. READ-ONLY: this
script never removes, merges, or mutates anything -- it only prints receipts.

Run from repo root (or any linked worktree -- `git worktree list` resolves
the FULL set regardless of which linked worktree it is invoked from):
    PYTHONPATH=src python scripts/maintenance/worktree_sentinel_sweep_report.py
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    from des.adapters.driven.refactor.git_worktree_adapter import GitWorktreeAdapter
    from des.application.worktree_sentinel_sweep import sweep_worktrees
    from des.application.worktree_triage_collector import resolve_target_branch

    repo = Path.cwd()
    target_branch = resolve_target_branch(repo)
    report = sweep_worktrees(
        repo=repo, worktree_port=GitWorktreeAdapter(), target_branch=target_branch
    )

    if not report.entries:
        print("No linked worktrees found.")
        return 0

    counts: dict[str, int] = {}
    for entry in report.entries:
        state = entry.receipt.state.value
        counts[state] = counts.get(state, 0) + 1
        print(f"{state:<20} {entry.handle.path} (branch={entry.handle.branch})")
        for finding in entry.receipt.evidence:
            print(f"    - {finding.category}: {finding.what}")

    print()
    print(f"Reference branch: {target_branch!r}")
    print(f"Total linked worktrees swept: {len(report.entries)}")
    for state, count in sorted(counts.items()):
        print(f"  {state}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
